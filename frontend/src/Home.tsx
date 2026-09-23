import { useEffect, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  api, streamJobEvents, REPORT_TYPES, QUALITY_THRESHOLD, MAX_ITERATIONS,
} from './api';
import type { ProgressEvent, StageKey, GenerationResult } from './api';
import {
  IconCheck, IconCopy, IconDownload, IconRefresh, IconSearchWeb, IconPen, IconScale, IconLoop,
} from './ui';

const REPORT_TYPE_KEYS = Object.keys(REPORT_TYPES) as (keyof typeof REPORT_TYPES)[];

const EXAMPLE_TOPICS = [
  'Quantum computing advances',
  'EV market landscape 2026',
  'CRISPR gene editing breakthroughs',
  'Kubernetes best practices',
];

const STAGES: { key: StageKey; label: string; icon: (p: { size?: number }) => React.ReactElement }[] = [
  { key: 'research', label: 'RESEARCH', icon: IconSearchWeb },
  { key: 'synthesize', label: 'WRITE', icon: IconPen },
  { key: 'critique', label: 'CRITIQUE', icon: IconScale },
  { key: 'refine', label: 'REFINE', icon: IconLoop },
];

interface ScoreRecord {
  iteration: number;
  score: number | null;
}

interface LogLine {
  time: string;
  kind: 'run' | 'ok' | 'err';
  text: string;
}

const now = () => new Date().toLocaleTimeString([], { hour12: false });

/** One generation run: form -> live pipeline -> results. */
export default function Home({ onGenerated, toast }: {
  onGenerated: () => void;
  toast: (kind: 'ok' | 'err', msg: string) => void;
}) {
  const [topic, setTopic] = useState('');
  const [reportType, setReportType] = useState<keyof typeof REPORT_TYPES>('academic');
  const [running, setRunning] = useState(false);
  const [activeStage, setActiveStage] = useState<StageKey | null>(null);
  const [doneStages, setDoneStages] = useState<Set<StageKey>>(new Set());
  const [progress, setProgress] = useState(0);
  const [scores, setScores] = useState<ScoreRecord[]>([]);
  const [sources, setSources] = useState<number | null>(null);
  const [log, setLog] = useState<LogLine[]>([]);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef(0);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  // Elapsed-seconds ticker while generating.
  useEffect(() => {
    if (running) {
      startedAt.current = Date.now();
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt.current) / 1000)), 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [running]);

  // Auto-scroll log console.
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [log]);

  const reset = () => {
    setActiveStage(null);
    setDoneStages(new Set());
    setProgress(0);
    setScores([]);
    setSources(null);
    setLog([]);
    setResult(null);
    setError(null);
    setElapsed(0);
  };

  const addLog = (kind: LogLine['kind'], text: string) =>
    setLog((prev) => [...prev.slice(-60), { time: now(), kind, text }]);

  const handleEvent = (ev: ProgressEvent) => {
    const stage = ev.stage as StageKey;
    if (ev.status === 'start') {
      setActiveStage(stage);
      addLog('run', ev.message ?? stage);
    } else if (ev.status === 'done') {
      addLog('ok', ev.message ?? stage);
      if (stage === 'research' && typeof ev.sources === 'number') setSources(ev.sources);
      if (stage === 'critique' && ev.score != null) {
        setScores((prev) => [...prev, { iteration: ev.iteration ?? prev.length + 1, score: ev.score! }]);
        if (ev.score >= QUALITY_THRESHOLD) {
          setDoneStages((prev) => new Set([...prev, 'critique', 'refine']));
        }
      }
    } else if (ev.status === 'error') {
      addLog('err', ev.message ?? 'pipeline error');
    }

    const it = ev.iteration ?? 1;
    let pct: number = { start: 5, research: 15, synthesize: 35, critique: 55, refine: 80, done: 100 }[ev.stage] ?? 10;
    if (ev.stage === 'critique') pct = Math.min(90, 45 + 15 * it);
    setProgress(pct);
  };

  const handleEnd = (jobId: string, ok: boolean) => {
    if (!ok) {
      setRunning(false);
      setError('Connection to the generation stream was lost.');
      return;
    }
    api.getResult(jobId)
      .then((r) => {
        setResult(r);
        setProgress(100);
        setActiveStage(null);
        setDoneStages(new Set(STAGES.map((s) => s.key)));
        onGenerated();
        toast('ok', `Report ready — scored ${r.final_score ?? '?'}/10`);
      })
      .catch((e) => setError(e.message))
      .finally(() => setRunning(false));
  };

  const start = async () => {
    if (!topic.trim()) {
      setError('Please enter a research topic!');
      return;
    }
    reset();
    setRunning(true);
    addLog('run', `Starting generation for “${topic.trim()}”`);
    try {
      const { job_id } = await api.startGeneration(topic.trim(), reportType);
      streamJobEvents(job_id, handleEvent, (ok) => handleEnd(job_id, ok));
    } catch (e) {
      setRunning(false);
      setError((e as Error).message);
      addLog('err', (e as Error).message);
    }
  };

  const retry = () => {
    reset();
    // Keep the same topic/type; just run again.
    setTimeout(() => { start(); }, 0);
  };

  const stageState = (key: StageKey): 'active' | 'done' | '' => {
    if (activeStage === key) return 'active';
    if (doneStages.has(key) && activeStage !== key) return 'done';
    return '';
  };

  return (
    <>
      {/* ---------------- Generation form ---------------- */}
      <section className="card">
        <div className="form-grid">
          <div className="field" style={{ flex: 3 }}>
            <span className="field-label">Research topic</span>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="What should the agents research?"
              disabled={running}
              onKeyDown={(e) => { if (e.key === 'Enter' && !running) start(); }}
              autoFocus
            />
          </div>
          <button className="btn btn-primary btn-lg" onClick={start} disabled={running} style={{ alignSelf: 'flex-end' }}>
            {running ? <>Generating…</> : <>Run agents</>}
          </button>
        </div>

        <div className="field" style={{ marginTop: 12 }}>
          <span className="field-label">Report style</span>
          <div className="segmented">
            {REPORT_TYPE_KEYS.map((k) => (
              <button
                key={k}
                className={`segment ${reportType === k ? 'active' : ''}`}
                onClick={() => setReportType(k)}
                disabled={running}
              >
                {REPORT_TYPES[k].label}
              </button>
            ))}
          </div>
          <div className="segment-desc">{REPORT_TYPES[reportType].desc}</div>
        </div>

        <div className="chip-row">
          <span className="chip-label">Try:</span>
          {EXAMPLE_TOPICS.map((t) => (
            <button key={t} className="chip" onClick={() => setTopic(t)} disabled={running}>{t}</button>
          ))}
        </div>

        <p className="text-3 small" style={{ margin: '12px 0 0' }}>
          Quality target ≥ {QUALITY_THRESHOLD}/10 and the {MAX_ITERATIONS}-iteration refinement loop
          run automatically in the background.
        </p>
      </section>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* ---------------- Live pipeline ---------------- */}
      {(running || (progress > 0 && !result)) && (
        <section className="card gen-panel">
          <div className="gen-header">
            <div className="gen-status">
              <span className="spinner" />
              <span>Generating report</span>
            </div>
            <span className="timer mono">{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</span>
          </div>

          <div className="steps">
            {STAGES.map((s, i) => {
              const st = stageState(s.key);
              const Icon = s.icon;
              return (
                <StepGroup key={s.key} icon={<Icon size={15} />} label={s.label} state={st}
                  lineState={i < STAGES.length - 1 ? stageState(STAGES[i + 1].key) : null} />
              );
            })}
          </div>

          <div className="progress-row">
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="progress-pct">{progress}%</span>
          </div>

          {scores.length > 0 && (
            <div className="iters" style={{ marginBottom: 14 }}>
              {scores.map((s, i) => (
                <span key={i} className={`iter-chip ${(s.score ?? 0) >= QUALITY_THRESHOLD ? 'pass' : 'fail'}`}>
                  iter {s.iteration} · {s.score != null ? s.score.toFixed(1) : '—'}
                </span>
              ))}
            </div>
          )}

          <div className="log-console">
            {log.map((l, i) => (
              <div key={i} className={`log-line ${l.kind}`}>
                <span className="log-time">{l.time}</span>
                <span className="log-msg">{l.text}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </section>
      )}

      {/* ---------------- Results ---------------- */}
      {result && (
        <Results
          result={result}
          scores={scores}
          sources={sources}
          elapsed={elapsed}
          onRetry={retry}
          toast={toast}
        />
      )}
    </>
  );
}

function StepGroup({ icon, label, state, lineState }: {
  icon: React.ReactNode;
  label: string;
  state: 'active' | 'done' | '';
  lineState: 'active' | 'done' | '' | null;
}) {
  const lineFilled = lineState === 'done' || lineState === 'active';
  const lineFlowing = lineState === 'active';
  return (
    <>
      <div className={`step ${state}`}>
        <div className="step-dot">{state === 'done' ? <IconCheck size={14} /> : icon}</div>
        <div className="step-label">{label}</div>
      </div>
      {lineState !== null && (
        <div className={`step-line ${lineFilled ? 'filled' : ''} ${lineFlowing ? 'flowing' : ''}`} />
      )}
    </>
  );
}

// ============================================================================
// RESULTS
// ============================================================================

function Results({ result, scores, sources, elapsed, onRetry, toast }: {
  result: GenerationResult;
  scores: ScoreRecord[];
  sources: number | null;
  elapsed: number;
  onRetry: () => void;
  toast: (kind: 'ok' | 'err', msg: string) => void;
}) {
  const [tab, setTab] = useState<'report' | 'eval' | 'loop' | 'meta'>('report');
  const review = result.final_review;
  const scoreAvg = review?.score?.average ?? result.final_score ?? 0;
  const passed = result.quality_threshold_met;

  const copyMd = async () => {
    try {
      await navigator.clipboard.writeText(result.final_report ?? '');
      toast('ok', 'Report copied to clipboard');
    } catch {
      toast('err', 'Could not access clipboard');
    }
  };

  const downloadMd = () => {
    const blob = new Blob([result.final_report ?? ''], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `report_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `report_metadata_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      {/* Score header */}
      <section className="results-head">
        <div className="score-ring-wrap">
          <ScoreRing score={scoreAvg} passed={passed} />
          <div className="verdict">
            <div className="verdict-title">
              {passed ? 'Quality target met' : 'Below target'}
              <span className={passed ? 'pass-badge' : 'warn-badge'}>
                {passed ? 'PASSED' : `MAX ${MAX_ITERATIONS} LOOPS`}
              </span>
            </div>
            <div className="verdict-sub">
              {result.topic} · {REPORT_TYPES[result.report_type as keyof typeof REPORT_TYPES]?.label ?? result.report_type}
            </div>
          </div>
        </div>
        <div className="head-stats">
          <div className="head-stat">
            <span className="head-stat-value">{result.iterations_completed}</span>
            <span className="head-stat-label">iterations</span>
          </div>
          <div className="head-stat">
            <span className="head-stat-value">{scores.length > 1 ? `+${(scores[scores.length - 1].score ?? 0) - (scores[0].score ?? 0) >= 0 ? '+' : ''}${((scores[scores.length - 1].score ?? 0) - (scores[0].score ?? 0)).toFixed(1)}` : '—'}</span>
            <span className="head-stat-label">score delta</span>
          </div>
          <div className="head-stat">
            <span className="head-stat-value">{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</span>
            <span className="head-stat-label">generation time</span>
          </div>
        </div>
      </section>

      {/* Tabs */}
      <div className="tabs">
        {([['report', 'Report'], ['eval', 'Evaluation'], ['loop', 'Iteration Loop'], ['meta', 'Metadata']] as const).map(
          ([key, label]) => (
            <button key={key} className={`tab ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)}>
              {label}
            </button>
          ),
        )}
      </div>

      <div className="tab-panel">
        {tab === 'report' && (
          <section className="card">
            <div className="report-actions">
              <button className="btn btn-ghost" onClick={copyMd}><IconCopy size={13} /> Copy</button>
              <button className="btn btn-ghost" onClick={downloadMd}><IconDownload size={13} /> .md</button>
              <button className="btn btn-ghost" onClick={downloadJson}><IconDownload size={13} /> .json</button>
              <button className="btn btn-ghost" onClick={onRetry}><IconRefresh size={13} /> Run again</button>
            </div>
            <div className="md-body">
              <Markdown remarkPlugins={[remarkGfm]}>{result.final_report || '_No report generated._'}</Markdown>
            </div>
          </section>
        )}

        {tab === 'eval' && review && (
          <section className="card">
            <div className="metrics">
              <Metric label="Final score" value={`${scoreAvg.toFixed(1)}/10`} />
              <Metric label="Target" value={`≥ ${QUALITY_THRESHOLD}`} />
              <Metric label="Iterations" value={`${result.iterations_completed}/${MAX_ITERATIONS}`} />
              <Metric label="Sources" value={sources != null ? String(sources) : '—'} />
            </div>

            <div className="dims">
              {([
                ['Factual accuracy', review.score.factual_accuracy],
                ['Completeness', review.score.completeness],
                ['Clarity & readability', review.score.clarity],
                ['Structure', review.score.structure],
                ['Depth', review.score.depth],
              ] as const).map(([name, val]) => (
                <div key={name} className="dim">
                  <span className="dim-name">{name}</span>
                  <div className="dim-track">
                    <div className={`dim-fill ${val >= 7 ? 'good' : val >= 5 ? 'mid' : 'bad'}`}
                      style={{ width: 0, animation: `dimGrow 0.8s cubic-bezier(0.25,1,0.4,1) ${0.1}s forwards`, ['--w' as never]: `${Math.min(val, 10) * 10}%` }} />
                  </div>
                  <span className="dim-val">{val}/10</span>
                </div>
              ))}
            </div>

            <Feedback title="Strengths" items={review.strengths} kind="good" />
            <Feedback title="Weaknesses" items={review.weaknesses} kind="warn" />
            <Feedback title="Suggestions" items={review.suggestions} kind="info" />
          </section>
        )}

        {tab === 'loop' && (
          <section className="card">
            <p className="text-2 small" style={{ marginTop: 0 }}>
              The critic scores every draft; the refinement agent rewrites until the average
              reaches <b>{QUALITY_THRESHOLD}/10</b> or <b>{MAX_ITERATIONS} iterations</b> complete.
            </p>

            {scores.length === 0 ? (
              <div className="fb-item good">
                <span className="fb-icon"><IconCheck size={13} /></span>
                Passed on the first review — no refinement needed.
              </div>
            ) : (
              <ScoreChart scores={scores} />
            )}

            <div className="refine-list" style={{ marginTop: 16 }}>
              {(result.refinement_history ?? []).map((h) => (
                <details key={h.iteration} className="refine-item">
                  <summary>
                    <span className="mono text-3">#{h.iteration}</span>
                    Refined — previous score {h.previous_score}/10
                  </summary>
                  <div className="refine-body">
                    <b className="small text-2">Changes applied:</b>
                    <ul>
                      {(h.changes_made ?? []).map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  </div>
                </details>
              ))}
            </div>
          </section>
        )}

        {tab === 'meta' && (
          <section className="card">
            <div className="meta-grid">
              <MetaRow k="Topic" v={result.topic} />
              <MetaRow k="Report type" v={result.report_type} />
              <MetaRow k="Generated" v={result.timestamp} />
              <MetaRow k="Generation time" v={`${elapsed}s`} />
              <MetaRow k="Quality target" v={`≥ ${QUALITY_THRESHOLD}/10`} />
              <MetaRow k="Max loop" v={`${MAX_ITERATIONS} iterations`} />
              {sources != null && <MetaRow k="Research sources" v={String(sources)} />}
            </div>
            <details className="refine-item">
              <summary><span className="mono text-3">JSON</span> Full metadata</summary>
              <pre className="json-view">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </section>
        )}
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

function MetaRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="meta-row">
      <b>{k}</b>
      <span className="text-2" style={{ textAlign: 'right' }}>{v}</span>
    </div>
  );
}

function Feedback({ title, items, kind }: { title: string; items: string[]; kind: 'good' | 'warn' | 'info' }) {
  if (!items?.length) return null;
  return (
    <div className="fb-section">
      <div className="fb-title">{title}</div>
      {items.map((s, i) => (
        <div key={i} className={`fb-item ${kind}`}>
          <span className="fb-icon">{kind === 'good' ? '✓' : kind === 'warn' ? '△' : '→'}</span>
          <span>{s}</span>
        </div>
      ))}
    </div>
  );
}

function ScoreRing({ score, passed }: { score: number; passed: boolean }) {
  const R = 26;
  const C = 2 * Math.PI * R;
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDrawn(score / 10), 60);
    return () => clearTimeout(t);
  }, [score]);

  return (
    <div className="score-ring">
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle className="ring-bg" cx="32" cy="32" r={R} fill="none" strokeWidth="5" />
        <circle
          className={`ring-val ${passed ? 'pass' : 'fail'}`}
          cx="32" cy="32" r={R} fill="none" strokeWidth="5" strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - drawn)}
        />
      </svg>
      <div className="ring-text">{score.toFixed(1)}</div>
    </div>
  );
}

function ScoreChart({ scores }: { scores: ScoreRecord[] }) {
  const W = 560;
  const H = 150;
  const PAD_X = 26;
  const PAD_BOT = 24;
  const PAD_TOP = 12;
  const n = Math.max(scores.length, 2);
  const x = (i: number) => PAD_X + (i / (n - 1)) * (W - 2 * PAD_X);
  const y = (s: number) => PAD_TOP + (1 - s / 10) * (H - PAD_TOP - PAD_BOT);

  const pts = scores.map((s, i) => `${x(i)},${y(s.score ?? 0)}`).join(' ');
  const area = `${PAD_X},${H - PAD_BOT} ${pts} ${x(scores.length - 1)},${H - PAD_BOT}`;

  return (
    <div className="chart-wrap">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
        {[0, 2.5, 5, 7.5, 10].map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={PAD_X} x2={W - PAD_X} y1={y(v)} y2={y(v)} />
            <text className="chart-label" x={4} y={y(v) + 3}>{v}</text>
          </g>
        ))}
        <line className="chart-threshold" x1={PAD_X} x2={W - PAD_X} y1={y(QUALITY_THRESHOLD)} y2={y(QUALITY_THRESHOLD)} />
        <polygon className="chart-area" points={area} />
        <polyline className="chart-line" points={pts} />
        {scores.map((s, i) => (
          <circle key={i} className={`chart-dot ${(s.score ?? 0) >= QUALITY_THRESHOLD ? 'pass' : ''}`}
            cx={x(i)} cy={y(s.score ?? 0)} r="4">
            <title>{`iter ${s.iteration}: ${s.score ?? '—'}/10`}</title>
          </circle>
        ))}
        {scores.map((s, i) => (
          <text key={i} className="chart-label" x={x(i)} y={H - 6} textAnchor="middle">i{s.iteration}</text>
        ))}
      </svg>
    </div>
  );
}
