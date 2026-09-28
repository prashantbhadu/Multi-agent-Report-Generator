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
import os
import queue
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from auth import (create_access_token, hash_password, require_user,
                  verify_password)
import database
from database import create_user, get_user_by_email
from gmail_service import (build_authorize_url, exchange_code, is_connected,
                           _pop_state, store_connection)
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

    def __init__(self, topic: str, report_type: str, user_id: str,
                 email_requested: bool = False, email_recipient: str | None = None):
        self.id = uuid.uuid4().hex
        self.topic = topic
        self.report_type = report_type
        self.user_id = user_id
        self.email_requested = email_requested
        self.email_recipient = email_recipient
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
                email_requested=self.email_requested,
                email_recipient=self.email_recipient,
                user_id=self.user_id,
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

database.init_db()

_cors_origins = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]
# Extra browser origins (e.g. the deployed frontend on Vercel), comma-separated.
if extra := os.getenv("CORS_ORIGINS", ""):
    _cors_origins += [o.strip() for o in extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# AUTH (signup / login / me)
# ============================================================================

@app.post("/api/auth/signup")
def signup(payload: dict) -> dict:
    """Create an account; returns a JWT for immediate login."""
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    try:
        user = create_user(email, hash_password(password))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    return {"token": create_access_token(user["id"], user["email"]),
            "user": {"id": user["id"], "email": user["email"]}}


@app.post("/api/auth/login")
def login(payload: dict) -> dict:
    """Verify credentials and return a JWT."""
    from auth import hash_password, verify_password

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return {"token": create_access_token(user["id"], user["email"]),
            "user": {"id": user["id"], "email": user["email"]}}


@app.get("/api/auth/me")
def me(user: sqlite3.Row = Depends(require_user)) -> dict:
    """Return the authenticated user's profile + Gmail connection state."""
    return {
        "id": user["id"],
        "email": user["email"],
        "gmail_connected": is_connected(user["id"]),
    }


# ============================================================================
# GMAIL (OAuth2 connect + send)
# ============================================================================

@app.get("/api/gmail/authorize")
def gmail_authorize(token: str | None = None) -> RedirectResponse:
    """Redirect the browser to Google's consent screen.

    Browser navigation cannot send an Authorization header, so the frontend
    appends ?token=<jwt> and the user is resolved from it.
    """
    from auth import decode_token
    from database import get_user_by_id

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session token. Please log in again.")
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Account no longer exists. Please log in again.")
    return RedirectResponse(build_authorize_url(user["id"]), status_code=302)


@app.get("/api/gmail/callback")
def gmail_callback(code: str | None = None, state: str | None = None,
                   error: str | None = None) -> RedirectResponse:
    """OAuth redirect target: exchange code, store tokens, return to the UI."""
    frontend = "http://localhost:5173/settings"
    if error or not code or not state:
        return RedirectResponse(f"{frontend}?gmail=denied", status_code=302)

    user_id = _pop_state(state)
    if not user_id:
        return RedirectResponse(f"{frontend}?gmail=expired", status_code=302)

    try:
        tokens = exchange_code(code)
        gmail_email = store_connection(user_id, tokens)
    except Exception:
        return RedirectResponse(f"{frontend}?gmail=error", status_code=302)

    suffix = f"&email={gmail_email}" if gmail_email else ""
    return RedirectResponse(f"{frontend}?gmail=connected{suffix}", status_code=302)


@app.get("/api/gmail/status")
def gmail_status(user: sqlite3.Row = Depends(require_user)) -> dict:
    """Whether the user's Gmail account is connected."""
    row = database.get_gmail_token(user["id"])
    return {"connected": is_connected(user["id"]),
            "email": row["email"] if row else None}


@app.post("/api/gmail/send")
def gmail_send(payload: dict, user: sqlite3.Row = Depends(require_user)) -> dict:
    """Email a generated report to a recipient via the user's Gmail."""
    from gmail_service import send_report_email

    recipient = (payload.get("recipient") or "").strip()
    report_name = (payload.get("report_name") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = payload.get("body") or ""

    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=400, detail="Please enter a valid recipient email.")
    if not body:
        raise HTTPException(status_code=400, detail="Nothing to send — report body is empty.")
    if not subject:
        subject = f"Research report: {report_name or 'ReportForge'}"

    message_id = send_report_email(user, recipient, subject, body, report_name or None)
    row = database.record_email(user["id"], recipient=recipient, subject=subject,
                                status="sent", report_name=report_name or None,
                                message_id=message_id)
    return {"id": row["id"], "status": "sent", "recipient": recipient}


@app.get("/api/emails")
def list_emails(user: sqlite3.Row = Depends(require_user)) -> dict:
    """Sent-email history for the signed-in user."""
    rows = database.list_emails(user["id"])
    return {"emails": [
        {"id": r["id"], "recipient": r["recipient"], "subject": r["subject"],
         "status": r["status"], "error": r["error"],
         "created_at": r["created_at"]}
        for r in rows
    ]}


@app.get("/api/config")
def get_config(user: sqlite3.Row = Depends(require_user)) -> dict:
    """Fixed run parameters shown (read-only) in the UI."""
    return {"quality_threshold": QUALITY_THRESHOLD, "max_iterations": MAX_ITERATIONS}


@app.post("/api/generate")
def start_generation(payload: dict, user: sqlite3.Row = Depends(require_user)) -> dict:
    topic = (payload.get("topic") or "").strip()
    report_type = payload.get("report_type") or "academic"
    if not topic:
        raise HTTPException(status_code=400, detail="Please enter a research topic!")
    if report_type not in ("academic", "business", "technical", "news-style"):
        raise HTTPException(status_code=400, detail=f"Invalid report type: {report_type}")

    # Email Agent request (supervisor decides after the final report)
    email_requested = bool(payload.get("email_requested"))
    email_recipient = (payload.get("email_recipient") or "").strip() or user["email"]

    _cleanup_old_jobs()
    job = Job(topic, report_type, user_id=user["id"],
              email_requested=email_requested, email_recipient=email_recipient)
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
