import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import type { ReportSummary } from './api';
import { IconDownload, IconFile, IconRefresh, IconTrash } from './ui';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export default function History({ refreshKey, toast }: {
  refreshKey: number;
  toast: (kind: 'ok' | 'err', msg: string) => void;
}) {
  const [reports, setReports] = useState<ReportSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(() => {
    api.listReports()
      .then((r) => { setReports(r.reports); setError(null); })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  const handleDelete = async (name: string) => {
    if (confirming !== name) {
      setConfirming(name);
      setTimeout(() => setConfirming((c) => (c === name ? null : c)), 3000);
      return;
    }
    setConfirming(null);
    try {
      await api.deleteReport(name);
      toast('ok', 'Report deleted');
      load();
    } catch (e) {
      toast('err', (e as Error).message);
    }
  };

  const filtered = (reports ?? []).filter((r) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      r.topic.toLowerCase().includes(q) ||
      r.report_type.toLowerCase().includes(q) ||
      r.name.toLowerCase().includes(q)
    );
  });

  return (
    <>
      <div className="history-toolbar">
        <input
          className="search-input"
          placeholder="Search by topic, type, or filename…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-ghost" onClick={load} title="Refresh">
          <IconRefresh size={13} /> Refresh
        </button>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {reports === null && !error && <div className="card text-3">Loading reports…</div>}

      {reports !== null && reports.length === 0 && (
        <div className="card empty-state">
          <IconFile size={30} />
          <b>No reports yet</b>
          <span className="small">Generate your first report from the Generate page.</span>
        </div>
      )}

      {reports !== null && reports.length > 0 && filtered.length === 0 && (
        <div className="card empty-state">
          <b>No matches</b>
          <span className="small">Nothing matches “{query}”.</span>
        </div>
      )}

      {filtered.map((r) => (
        <div key={r.name} className="report-row">
          <div className="report-icon"><IconFile /></div>
          <div className="report-info">
            <span className="report-title">{r.topic.trim() || r.name}</span>
            <span className="report-sub">
              <span className="mono">{r.quality_score.trim()}</span>
              <span>{timeAgo(r.modified)}</span>
              <span>{fmtSize(r.size)}</span>
              <span className="mono text-3">{r.name}</span>
            </span>
          </div>
          <span className="type-tag">{r.report_type}</span>
          <div className="row-actions">
            <a className="icon-btn" href={api.reportDownloadUrl(r.name)} download title="Download">
              <IconDownload />
            </a>
            <button
              className={`icon-btn ${confirming === r.name ? 'danger' : ''}`}
              onClick={() => handleDelete(r.name)}
              title={confirming === r.name ? 'Click again to confirm' : 'Delete'}
              style={confirming === r.name ? { color: 'var(--red)', background: 'var(--red-dim)' } : undefined}
            >
              <IconTrash />
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
