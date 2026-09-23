// Shared types + API client for the FastAPI backend.

export const QUALITY_THRESHOLD = 7.0;
export const MAX_ITERATIONS = 4;

export type ReportType = 'academic' | 'business' | 'technical' | 'news-style';

export const REPORT_TYPES: Record<ReportType, { label: string; desc: string }> = {
  academic: { label: '🎓 Academic', desc: 'Formal, cited, peer-review style' },
  business: { label: '💼 Business', desc: 'Executive summary, ROI and impact focus' },
  technical: { label: '🛠️ Technical', desc: 'Deep dive, architecture, precision' },
  'news-style': { label: '📰 News-Style', desc: 'Engaging, headline-first journalism' },
};

export const PIPELINE_STAGES = [
  { key: 'research', label: 'Research', icon: '🔍' },
  { key: 'synthesize', label: 'Writer', icon: '✍️' },
  { key: 'critique', label: 'Critic', icon: '🧐' },
  { key: 'refine', label: 'Refine', icon: '🔄' },
] as const;

export type StageKey = (typeof PIPELINE_STAGES)[number]['key'];

export interface ProgressEvent {
  stage: string;
  status?: 'start' | 'done' | 'error';
  iteration?: number | null;
  max_iterations?: number;
  message?: string;
  score?: number | null;
  sources?: number;
  threshold_met?: boolean;
}

export interface ReviewScore {
  factual_accuracy: number;
  completeness: number;
  clarity: number;
  structure: number;
  depth: number;
  average: number;
}

export interface FinalReview {
  score: ReviewScore;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  pass_criteria_met: boolean;
}

export interface GenerationResult {
  topic: string;
  report_type: string;
  final_report: string;
  final_score: number | null;
  iterations_completed: number;
  quality_threshold_met: boolean;
  final_review: FinalReview | null;
  refinement_history: { iteration: number; timestamp: string; previous_score: number; changes_made: string[] }[];
  timestamp: string;
}

export interface ReportSummary {
  name: string;
  size: number;
  modified: string;
  topic: string;
  report_type: string;
  quality_score: string;
  generated: string;
}

const API = 'http://localhost:8000/api';

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

async function handleEmpty(res: Response): Promise<void> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
}

export const api = {
  startGeneration: (topic: string, reportType: ReportType) =>
    fetch(`${API}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, report_type: reportType }),
    }).then(handle<{ job_id: string }>),

  getResult: (jobId: string) =>
    fetch(`${API}/jobs/${jobId}`).then(handle<GenerationResult>),

  getConfig: () =>
    fetch(`${API}/config`).then(handle<{ quality_threshold: number; max_iterations: number }>),

  listReports: () =>
    fetch(`${API}/reports`).then(handle<{ reports: ReportSummary[] }>),

  deleteReport: (name: string) =>
    fetch(`${API}/reports/${encodeURIComponent(name)}`, { method: 'DELETE' }).then(handleEmpty),

  reportDownloadUrl: (name: string) => `${API}/reports/${encodeURIComponent(name)}`,
};

/**
 * Subscribe to the job's SSE progress stream.
 * Returns an unsubscribe function.
 */
export function streamJobEvents(jobId: string, onEvent: (ev: ProgressEvent) => void, onEnd: (ok: boolean) => void) {
  const es = new EventSource(`${API}/jobs/${jobId}/events`);
  es.onmessage = (m) => {
    try {
      const ev = JSON.parse(m.data) as ProgressEvent;
      if (ev.stage === '_exit') return; // internal sentinel
      onEvent(ev);
    } catch { /* ignore malformed events */ }
  };
  es.addEventListener('end', () => {
    es.close();
    onEnd(true);
  });
  es.onerror = () => {
    es.close();
    onEnd(false);
  };
  return () => es.close();
}
