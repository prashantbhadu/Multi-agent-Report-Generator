import { useEffect, useState } from 'react';
import Home from './Home';
import History from './History';
import Settings from './Settings';
import { api } from './api';
import { IconHome, IconLibrary, IconSettings, IconSpark, ToastStack, useToasts } from './ui';

type Page = 'home' | 'history' | 'settings';

const NAV: { key: Page; label: string; icon: (p: { size?: number }) => React.ReactElement }[] = [
  { key: 'home', label: 'Generate', icon: IconHome },
  { key: 'history', label: 'History', icon: IconLibrary },
  { key: 'settings', label: 'Settings', icon: IconSettings },
];

const PAGE_META: Record<Page, { title: string; hint: string }> = {
  home: { title: 'Generate', hint: 'Research → write → critique → refine, fully automatic' },
  history: { title: 'History', hint: 'Every report you have generated, saved locally' },
  settings: { title: 'Settings', hint: 'Pipeline parameters and environment configuration' },
};

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const { toasts, push, dismiss } = useToasts();

  // Poll the backend so the status dot is always truthful.
  useEffect(() => {
    let cancelled = false;
    const check = () => {
      api.getConfig()
        .then(() => { if (!cancelled) setApiOnline(true); })
        .catch(() => { if (!cancelled) setApiOnline(false); });
    };
    check();
    const iv = setInterval(check, 15000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  // Keyboard shortcuts: 1/2/3 to switch pages (ignored while typing).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const idx = ['1', '2', '3'].indexOf(e.key);
      if (idx >= 0) setPage(NAV[idx].key);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><IconSpark size={16} /></div>
          <div>
            <div className="brand-name">ReportForge</div>
            <div className="brand-sub">multi-agent v2.0</div>
          </div>
        </div>

        <nav className="nav">
          <div className="nav-section">Workspace</div>
          {NAV.map((n, i) => {
            const Icon = n.icon;
            return (
              <button key={n.key} className={`nav-link ${page === n.key ? 'active' : ''}`} onClick={() => setPage(n.key)}>
                <Icon size={16} />
                <span>{n.label}</span>
                <span className="kbd" style={{ marginLeft: 'auto', opacity: 0.6 }}>{i + 1}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="status-line">
            <span className={`status-dot ${apiOnline === true ? 'online' : apiOnline === false ? 'offline' : 'checking'}`} />
            <span>{apiOnline === true ? 'API connected' : apiOnline === false ? 'API offline' : 'Connecting…'}</span>
          </div>
          <div className="status-line">
            <span>≥ 7.0 target · max 4 loops</span>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{PAGE_META[page].title}</div>
          <div className="topbar-right">
            <span className="text-3 small">{PAGE_META[page].hint}</span>
            <span className="kbd">⌘K</span>
          </div>
        </header>

        <div className="content">
          <div className="page">
            {page === 'home' && (
              <Home
                onGenerated={() => setHistoryRefreshKey((k) => k + 1)}
                toast={(kind, msg) => push(kind, msg)}
              />
            )}
            {page === 'history' && (
              <History refreshKey={historyRefreshKey} toast={(kind, msg) => push(kind, msg)} />
            )}
            {page === 'settings' && <Settings />}
          </div>
        </div>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
