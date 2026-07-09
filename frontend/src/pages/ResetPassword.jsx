import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch, parseApiResponse } from '../api';

function Field({ label, type = 'text', value, onChange, onKeyDown, autoComplete, placeholder }) {
  return (
    <div className="group">
      <label className="mb-1.5 block text-xs font-medium tracking-wide text-brand-muted">{label}</label>
      <input
        type={type}
        className="w-full rounded-xl border border-brand-glow/15 bg-brand-accent/25 px-4 py-3 text-sm
                  text-brand-dirty shadow-[inset_0_1px_2px_rgba(0,0,0,0.2)] placeholder:text-brand-muted/60
                  transition focus:border-brand-glow/60 focus:bg-brand-accent/40 focus:outline-none focus:ring-2
                  focus:ring-brand-glow/30"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        autoComplete={autoComplete}
      />
    </div>
  );
}

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (!token) setError('Invalid reset link. Request a new one from the sign-in page.');
  }, [token]);

  const submit = async () => {
    setError('');
    setMessage('');
    if (!token) return;
    if (password !== confirm) return setError('Passwords do not match');
    setLoading(true);
    try {
      const res = await apiFetch('/api/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password }),
      });
      const { data, ok, status } = await parseApiResponse(res);
      if (status === 429) {
        setError(data.error || 'Too many attempts. Wait a few minutes and try again.');
        return;
      }
      if (ok) setMessage(data.message || 'Password updated.');
      else setError(data.error || 'Reset failed');
    } catch {
      setError('Could not reach the server. Check that the app is running and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page flex min-h-[calc(100vh-32px)] items-center justify-center px-3 py-4">
      <div className="login-modal-enter w-full max-w-md overflow-hidden rounded-3xl border border-brand-glow/10 bg-brand-accent/20 p-8 shadow-modal-lg">
        <h1 className="text-2xl font-semibold text-brand-dirty">Choose a new password</h1>
        <p className="mt-2 text-sm text-brand-muted">
          At least 8 characters with uppercase, number, and special character.
        </p>
        {error && (
          <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
        )}
        {message && (
          <div className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</div>
        )}
        {token && !message && (
          <>
            <div className="mt-6 space-y-4">
              <Field
                label="New password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••"
              />
              <Field
                label="Confirm password"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                autoComplete="new-password"
                placeholder="••••••••"
              />
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={submit}
              className="mt-6 w-full rounded-xl bg-gradient-to-r from-brand-accent to-brand-bright py-3.5 text-sm font-semibold text-brand-dirty disabled:opacity-50"
            >
              {loading ? 'Updating…' : 'Update password'}
            </button>
          </>
        )}
        <p className="mt-5 text-center text-sm text-brand-muted">
          <Link to="/" className="text-brand-glow hover:underline">Back to sign in</Link>
          {!token && (
            <>
              {' · '}
              <Link to="/forgot-password" className="text-brand-glow hover:underline">Request new link</Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
