"""
FastAPI Backend for the Multi-Agent Report Generator.

Serves the React frontend with:
  - POST /api/generate          -> start a generation job, returns { job_id }
  - GET  /api/jobs/{id}/events  -> Server-Sent Events stream of live progress
  - GET  /api/jobs/{id}         -> final result (404 until finished)
  - GET  /api/config            -> fixed run parameters (threshold, max iterations)
  - GET  /api/reports           -> list saved reports (newest first)
  - GET  /api/reports/{name}    -> fetch a saved report
  - DELETE /api/reports/{name}  -> delete a saved report

Run with:  uvicorn api:app --reload --port 8000
"""

import json
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from report_generator import generate_report

# ============================================================================
# FIXED RUN PARAMETERS (managed in the background — not user-facing controls)
# ============================================================================

QUALITY_THRESHOLD = 7.0   # Reports must score >= 7.0/10 to pass
MAX_ITERATIONS = 4        # Refinement loop runs at most 4 cycles

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


class Job:
    """Tracks one generation run: queued progress events + final outcome."""

    def __init__(self, topic: str, report_type: str):
        self.id = uuid.uuid4().hex
        self.topic = topic
        self.report_type = report_type
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.result: dict | None = None
        self.error: str | None = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.created_at = time.time()

    def _run(self) -> None:
        def callback(event: dict) -> None:
            self.events.put(event)

        try:
            self.result = generate_report(
                topic=self.topic,
                report_type=self.report_type,
                quality_threshold=QUALITY_THRESHOLD,
                max_iterations=MAX_ITERATIONS,
                progress_callback=callback,
            )
        except Exception as e:  # surface pipeline errors to the UI
            self.error = str(e)
            self.events.put({"stage": "error", "status": "error", "message": str(e)})
        finally:
            self.events.put({"stage": "_exit"})
            self.done.set()


JOBS: dict[str, Job] = {}


def _cleanup_old_jobs(max_age_seconds: int = 3600) -> None:
    """Drop finished jobs older than an hour so the dict doesn't grow forever."""
    now = time.time()
    for job_id in list(JOBS):
        job = JOBS[job_id]
        if job.done.is_set() and now - job.created_at > max_age_seconds:
            JOBS.pop(job_id, None)


# ============================================================================
# HELPERS
# ============================================================================

def save_report(report_content: str, metadata: dict) -> str:
    """Persist a finished report to disk and return the filepath."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = REPORTS_DIR / f"report_{timestamp}.md"

    review = metadata.get("final_review") or {}
    score = review.get("score", {}) if isinstance(review, dict) else {}
    avg = score.get("average", metadata.get("final_score"))

    full_content = f"""# Research Report
**Topic:** {metadata.get('topic', 'N/A')}
**Report Type:** {metadata.get('report_type', 'N/A')}
**Generated:** {metadata.get('timestamp', 'N/A')}
**Quality Score:** {avg if avg is not None else 'N/A'}/10
**Quality Target:** >= {QUALITY_THRESHOLD}/10 (met: {metadata.get('quality_threshold_met', False)})
**Iterations:** {metadata.get('iterations_completed', 0)} of {MAX_ITERATIONS}

---

{report_content}

---

## Generation Metadata
- **Quality threshold:** {QUALITY_THRESHOLD}/10 (managed in background)
- **Max iteration loop:** {MAX_ITERATIONS}
- **Final Review:** {json.dumps(metadata.get('final_review'), indent=2, default=str)}
"""
    filename.write_text(full_content, encoding="utf-8")
    return str(filename)


# ============================================================================
# APP
# ============================================================================

app = FastAPI(title="Multi-Agent Report Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def get_config() -> dict:
    """Fixed run parameters shown (read-only) in the UI."""
    return {"quality_threshold": QUALITY_THRESHOLD, "max_iterations": MAX_ITERATIONS}


@app.post("/api/generate")
def start_generation(payload: dict) -> dict:
    topic = (payload.get("topic") or "").strip()
    report_type = payload.get("report_type") or "academic"
    if not topic:
        raise HTTPException(status_code=400, detail="Please enter a research topic!")
    if report_type not in ("academic", "business", "technical", "news-style"):
        raise HTTPException(status_code=400, detail=f"Invalid report type: {report_type}")

    _cleanup_old_jobs()
    job = Job(topic, report_type)
    JOBS[job.id] = job
    job.thread.start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}/events")
def stream_job_events(job_id: str):
    """SSE stream of pipeline progress events for one job."""
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")

    def event_stream():
        while True:
            try:
                ev = job.events.get(timeout=1.0)
            except queue.Empty:
                if job.done.is_set() and job.events.empty():
                    yield f"event: end\ndata: {json.dumps({'ok': job.error is None})}\n\n"
                    return
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(ev, default=str)}\n\n"
            if ev.get("stage") == "_exit":
                # Drain any remaining queued events before finishing.
                while not job.events.empty():
                    ev2 = job.events.get_nowait()
                    yield f"data: {json.dumps(ev2, default=str)}\n\n"
                yield f"event: end\ndata: {json.dumps({'ok': job.error is None})}\n\n"
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/{job_id}")
def get_job_result(job_id: str) -> dict:
    """Final result once the job has finished (blocks until done)."""
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")

    job.done.wait()
    if job.error:
        raise HTTPException(status_code=500, detail=job.error)
    return job.result


@app.get("/api/reports")
def list_reports() -> dict:
    files = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        meta = {}
        for line in content.split("\n")[:10]:
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip().lstrip("*").strip()] = value.strip().lstrip("*").strip()
        reports.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "topic": meta.get("Topic", "N/A"),
            "report_type": meta.get("Report Type", "N/A"),
            "quality_score": meta.get("Quality Score", "N/A"),
            "generated": meta.get("Generated", "N/A"),
        })
    return {"reports": reports}


@app.get("/api/reports/{name}")
def get_report(name: str):
    """Download a saved report file."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid report name")
    path = REPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type="text/markdown", filename=name)


@app.delete("/api/reports/{name}")
def delete_report(name: str) -> dict:
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid report name")
    path = REPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    path.unlink()
    return {"deleted": name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
