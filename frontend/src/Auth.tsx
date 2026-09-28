import { useState } from 'react';
import { api, setToken } from './api';
import { IconSpark } from './ui';

/** Full-screen login / signup gate shown when no valid session exists. */
export default function Auth({ onAuthed, toast }: {
  onAuthed: () => void;
  toast: (kind: 'ok' | 'err', msg: string) => void;
}) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === 'signup' && password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      const res = mode === 'login'
        ? await api.login(email.trim(), password)
        : await api.signup(email.trim(), password);
      setToken(res.token);
      toast('ok', mode === 'login' ? 'Welcome back!' : 'Account created — welcome!');
      onAuthed();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark"><IconSpark size={18} /></div>
          <div>
            <div className="brand-name">ReportForge</div>
            <div className="brand-sub">multi-agent report generation</div>
          </div>
        </div>

        <div className="segmented" style={{ marginBottom: 18 }}>
          <button className={`segment ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>Log in</button>
          <button className={`segment ${mode === 'signup' ? 'active' : ''}`} onClick={() => setMode('signup')}>Sign up</button>
        </div>

        <form onSubmit={submit}>
          <div className="field">
            <span className="field-label">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
              required
            />
          </div>

          <div className="field" style={{ marginTop: 12 }}>
            <span className="field-label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? 'At least 8 characters' : 'Your password'}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              required
            />
          </div>

          {mode === 'signup' && (
            <div className="field" style={{ marginTop: 12 }}>
              <span className="field-label">Confirm password</span>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat your password"
                autoComplete="new-password"
                required
              />
            </div>
          )}

          {error && <div className="error-banner" style={{ marginTop: 14 }}>⚠ {error}</div>}

          <button className="btn btn-primary btn-lg" type="submit" disabled={busy} style={{ width: '100%', marginTop: 16 }}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <p className="text-3 small" style={{ marginBottom: 0, textAlign: 'center' }}>
          {mode === 'login'
            ? 'New here? Switch to Sign up to create an account.'
            : 'Already registered? Switch to Log in.'}
        </p>
      </div>
    </div>
  );
}
