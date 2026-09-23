import { useEffect, useState } from 'react';
import { api, QUALITY_THRESHOLD, MAX_ITERATIONS } from './api';

export default function Settings() {
  const [config, setConfig] = useState<{ quality_threshold: number; max_iterations: number } | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api.getConfig()
      .then((c) => { setConfig(c); setOnline(true); })
      .catch(() => setOnline(false));
  }, []);

  return (
    <>
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
        <div className="card-title">
          Backend connection
          <span className={`small ${online === true ? 'text-green' : online === false ? 'text-red' : 'text-3'}`}>
            {online === true ? '● connected' : online === false ? '● offline' : '● checking'}
          </span>
        </div>
        <div className="env-grid">
          <div className="env-row">
            <span className="env-key">GROQ_API_KEY</span>
            <span className="env-desc">Groq LLM — writing, critique, and refinement</span>
          </div>
          <div className="env-row">
            <span className="env-key">TAVILY_API_KEY</span>
            <span className="env-desc">Tavily — web search and source discovery</span>
          </div>
        </div>
        <p className="text-3 small" style={{ marginBottom: 0 }}>
          Keys live in your <code>.env</code> file at the project root. The backend must be
          restarted after changing them.
        </p>
      </section>

      <section className="card">
        <div className="card-title">About</div>
        <div className="setting-row">
          <div>
            <div className="setting-name">ReportForge</div>
            <div className="setting-desc">Multi-agent report generation on LangGraph</div>
          </div>
          <span className="setting-value">v2.0</span>
        </div>
        <div className="setting-row">
          <div>
            <div className="setting-name">Stack</div>
            <div className="setting-desc">React · FastAPI · LangGraph · Groq · Tavily</div>
          </div>
          <span className="setting-value">local</span>
        </div>
      </section>
    </>
  );
}
