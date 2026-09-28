import { useEffect, useState } from 'react';
import { api, getToken, QUALITY_THRESHOLD, MAX_ITERATIONS } from './api';
import type { User } from './api';
import { IconExternal } from './ui';

/** Read the ?gmail=… result param after the OAuth redirect back to /settings. */
function consumeGmailParam(): string | null {
  const params = new URLSearchParams(window.location.search);
  const value = params.get('gmail');
  if (!value) return null;
  params.delete('gmail');
  params.delete('email');
  const qs = params.toString();
  window.history.replaceState({}, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`);
  return value;
}

export default function Settings({ user, onUserChanged, toast }: {
  user: User;
  onUserChanged: (u: User) => void;
  toast: (kind: 'ok' | 'err', msg: string) => void;
}) {
  const [config, setConfig] = useState<{ quality_threshold: number; max_iterations: number } | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [gmail, setGmail] = useState<{ connected: boolean; email: string | null } | null>(null);
  void online; // status dot now lives in the sidebar; kept for future use

  useEffect(() => {
    api.getConfig()
      .then((c) => { setConfig(c); setOnline(true); })
      .catch(() => setOnline(false));
  }, []);

  useEffect(() => {
    api.gmailStatus().then(setGmail).catch(() => setGmail({ connected: false, email: null }));
  }, [user.id]);

  // Surface the OAuth flow outcome (redirect lands on /settings?gmail=…).
  useEffect(() => {
    const outcome = consumeGmailParam();
    if (!outcome) return;
    if (outcome === 'connected') {
      toast('ok', 'Gmail connected!');
      api.me().then(onUserChanged).catch(() => {});
    } else if (outcome === 'denied') {
      toast('err', 'Gmail connection was cancelled.');
    } else if (outcome === 'expired') {
      toast('err', 'Connection request expired — please try again.');
    } else {
      toast('err', 'Gmail connection failed — check backend .env Google credentials.');
    }
  }, [toast, onUserChanged]);

  const connectGmail = () => {
    // Send the JWT so /api/gmail/authorize can bind the OAuth state to this user.
    window.location.href = `${api.gmailAuthorizeUrl()}?token=${encodeURIComponent(getToken() ?? '')}`;
  };

  return (
    <>
      <section className="card">
        <div className="card-title">Gmail connection</div>
        {!gmail || !gmail.connected ? (
          <div className="setting-row">
            <div>
              <div className="setting-name">Not connected</div>
              <div className="setting-desc">
                Connect your Gmail account to email generated reports. A Google consent
                screen opens; ReportForge stores only the OAuth tokens.
              </div>
            </div>
            <button className="btn btn-primary" onClick={connectGmail}>
              Connect Gmail
            </button>
          </div>
        ) : (
          <div className="setting-row">
            <div>
              <div className="setting-name">Connected{gmail.email ? ` as ${gmail.email}` : ''}</div>
              <div className="setting-desc">
                Reports you email are sent through your Gmail account and recorded in History → Emails.
              </div>
            </div>
            <span className="setting-value">● online</span>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-title">Pipeline parameters <span className="mono text-3">read-only</span></div>
        <div className="setting-row">
          <div>
            <div className="setting-name">Quality threshold</div>
            <div className="setting-desc">Minimum average critic score for a report to pass</div>
          </div>
          <span className="setting-value">≥ {config?.quality_threshold ?? QUALITY_THRESHOLD} / 10</span>
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-name">Max refinement iterations</div>
            <div className="setting-desc">Rewrite loop limit before finalizing regardless of score</div>
          </div>
          <span className="setting-value">{config?.max_iterations ?? MAX_ITERATIONS} cycles</span>
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-name">Enforcement</div>
            <div className="setting-desc">Both parameters are enforced server-side in api.py</div>
          </div>
          <span className="setting-value">background</span>
        </div>
      </section>

      <section className="card">
        <div className="card-title">Signed in</div>
        <div className="setting-row">
          <div>
            <div className="setting-name">{user.email}</div>
            <div className="setting-desc">Session is stored as a JWT in this browser (7-day expiry)</div>
          </div>
          <span className="setting-value">v2.0</span>
        </div>
      </section>

      <section className="card">
        <div className="card-title">Backend connection</div>
        <div className="env-grid">
          <div className="env-row">
            <span className="env-key">GROQ_API_KEY</span>
            <span className="env-desc">Groq LLM — writing, critique, and refinement</span>
          </div>
          <div className="env-row">
            <span className="env-key">TAVILY_API_KEY</span>
            <span className="env-desc">Tavily — web search and source discovery</span>
          </div>
          <div className="env-row">
            <span className="env-key">GOOGLE_CLIENT_ID / SECRET</span>
            <span className="env-desc">Google OAuth — Gmail connection (Settings → Connect Gmail)</span>
            <IconExternal size={12} />
          </div>
        </div>
        <p className="text-3 small" style={{ marginBottom: 0 }}>
          Keys live in your <code>.env</code> file at the project root. The backend must be
          restarted after changing them.
        </p>
      </section>
    </>
  );
}
