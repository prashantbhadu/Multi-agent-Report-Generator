import { useEffect, useState } from 'react';
import Home from './Home';
import History from './History';
import Settings from './Settings';
import Auth from './Auth';
import { api, getToken, setToken } from './api';
import type { User } from './api';
import { IconHome, IconLibrary, IconSettings, IconSpark, ToastStack, useToasts } from './ui';

type Page = 'home' | 'history' | 'settings';

const NAV: { key: Page; label: string; icon: (p: { size?: number }) => React.ReactElement }[] = [
  { key: 'home', label: 'Generate', icon: IconHome },
  { key: 'history', label: 'History', icon: IconLibrary },
  { key: 'settings', label: 'Settings', icon: IconSettings },
];

const PAGE_META: Record<Page, { title: string; hint: string }> = {
  home: { title: 'Generate', hint: 'Research → write → critique → refine, fully automatic' },
  history: { title: 'History', hint: 'Reports you generated and emails you sent' },
  settings: { title: 'Settings', hint: 'Gmail connection, pipeline parameters, environment' },
};

export default function App() {
  const [page, setPage] = useState<Page>('home');
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const { toasts, push, dismiss } = useToasts();

  // Restore the session from a stored JWT (if any).
  useEffect(() => {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    api.me()
      .then(setUser)
      .catch(() => setToken(null))   // invalid/expired -> forget it
      .finally(() => setChecking(false));
  }, []);

  // Poll the backend so the status dot is always truthful.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const check = () => {
      api.getConfig()
        .then(() => { if (!cancelled) setApiOnline(true); })
        .catch(() => { if (!cancelled) setApiOnline(false); });
    };
    check();
    const iv = setInterval(check, 15000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [user]);

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

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setPage('home');
    push('ok', 'Logged out');
  };

  // While the stored token is being validated, avoid flashing the auth gate.
  if (checking) {
    return (
      <div className="auth-wrap">
        <div className="auth-card text-3">Restoring session…</div>
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <Auth onAuthed={() => { api.me().then(setUser).catch(() => {}); }} toast={push} />
        <ToastStack toasts={toasts} onDismiss={dismiss} />
      </>
    );
  }

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
            <span className="user-email" title={user.email}>{user.email}</span>
            <button className="link-btn" onClick={handleLogout}>Log out</button>
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
                user={user}
                onGenerated={() => setHistoryRefreshKey((k) => k + 1)}
                toast={(kind, msg) => push(kind, msg)}
              />
            )}
            {page === 'history' && (
              <History refreshKey={historyRefreshKey} toast={(kind, msg) => push(kind, msg)} />
            )}
            {page === 'settings' && (
              <Settings
                user={user}
                onUserChanged={setUser}
                toast={(kind, msg) => push(kind, msg)}
              />
            )}
          </div>
        </div>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
