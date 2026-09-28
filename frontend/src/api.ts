// Shared types + API client for the FastAPI backend.

export const QUALITY_THRESHOLD = 7.0;
export const MAX_ITERATIONS = 4;

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'reportforge_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export interface User {
  id: string;
  email: string;
  gmail_connected?: boolean;
}

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

export type ReportType = 'academic' | 'business' | 'technical' | 'news-style';

export const REPORT_TYPES: Record<ReportType, { label: string; desc: string }> = {
  academic: { label: '🎓 Academic', desc: 'Formal, cited, peer-review style' },
  business: { label: '💼 Business', desc: 'Executive summary, ROI and impact focus' },
  technical: { label: '🛠️ Technical', desc: 'Deep dive, architecture, precision' },
  'news-style': { label: '📰 News-Style', desc: 'Engaging, headline-first journalism' },
};

export const PIPELINE_STAGES = [
  { key: 'supervisor', label: 'Supervisor', icon: '🧭' },
  { key: 'research', label: 'Research', icon: '🔍' },
  { key: 'synthesize', label: 'Writer', icon: '✍️' },
  { key: 'critique', label: 'Critic', icon: '🧐' },
  { key: 'refine', label: 'Refine', icon: '🔄' },
  { key: 'email', label: 'Email Agent', icon: '📧' },
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
  email_decision?: boolean;
}

export interface EmailResult {
  ok: boolean;
  status?: string;
  error?: string;
  note?: string;
  recipient?: string;
  message_id?: string;
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
  plan?: string | null;
  email_requested?: boolean;
  email_recipient?: string | null;
  email_result?: EmailResult | null;
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

export interface EmailRecord {
  id: string;
  recipient: string;
  subject: string;
  status: string;
  error: string | null;
  created_at: number;
}

const API = 'http://localhost:8000/api';

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch { /* ignore */ }
    // A rejected/expired token acts like being logged out.
    if (res.status === 401) setToken(null);
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
  // ---- auth ----
  signup: (email: string, password: string) =>
    fetch(`${API}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }).then(handle<{ token: string; user: User }>),

  login: (email: string, password: string) =>
    fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }).then(handle<{ token: string; user: User }>),

  me: () => fetch(`${API}/auth/me`, { headers: authHeaders() }).then(handle<User>),

  // ---- gmail ----
  gmailAuthorizeUrl: () => `${API}/gmail/authorize`,
  gmailStatus: () =>
    fetch(`${API}/gmail/status`, { headers: authHeaders() }).then(handle<{ connected: boolean; email: string | null }>),

  sendEmail: (payload: { recipient: string; subject: string; body: string; report_name?: string }) =>
    fetch(`${API}/gmail/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    }).then(handle<{ id: string; status: string; recipient: string }>),

  listEmails: () =>
    fetch(`${API}/emails`, { headers: authHeaders() }).then(handle<{ emails: EmailRecord[] }>),

  // ---- generation ----
  startGeneration: (topic: string, reportType: ReportType,
                    emailRequested = false, emailRecipient = '') =>
    fetch(`${API}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        topic,
        report_type: reportType,
        email_requested: emailRequested,
        email_recipient: emailRecipient,
      }),
    }).then(handle<{ job_id: string }>),

  getResult: (jobId: string) =>
    fetch(`${API}/jobs/${jobId}`, { headers: authHeaders() }).then(handle<GenerationResult>),

  getConfig: () =>
    fetch(`${API}/config`, { headers: authHeaders() }).then(handle<{ quality_threshold: number; max_iterations: number }>),

  listReports: () =>
    fetch(`${API}/reports`, { headers: authHeaders() }).then(handle<{ reports: ReportSummary[] }>),

  deleteReport: (name: string) =>
    fetch(`${API}/reports/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }).then(handleEmpty),

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
