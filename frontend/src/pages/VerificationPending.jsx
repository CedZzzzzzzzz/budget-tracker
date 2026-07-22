import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { apiFetch, parseApiResponse, primeCsrf } from '../api';

export default function VerificationPending() {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email || '');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(location.state?.message || 'Check your inbox for a verification link.');
  const [error, setError] = useState('');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    primeCsrf();
  }, []);

  const resend = async () => {
    const normalizedEmail = email.trim();
    setError('');
    setMessage('');
    if (!normalizedEmail || !normalizedEmail.includes('@')) {
      setError('Enter a valid email address.');
      return;
    }
    setLoading(true);
    try {
      const response = await apiFetch('/api/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email: normalizedEmail }),
      });
      const { data, ok, status } = await parseApiResponse(response);
      if (status === 429) {
        setError(data.error || 'Too many requests. Try again later.');
      } else if (ok) {
        setMessage(data.message || 'If the account needs verification, a new link has been sent.');
      } else {
        setError(data.error || 'Could not resend the verification link.');
      }
    } catch {
      setError('Could not reach the server. Try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page flex min-h-[calc(100vh-32px)] items-center justify-center px-3 py-4">
      <div className="login-modal-enter w-full max-w-md rounded-3xl border border-brand-glow/10 bg-brand-accent/20 p-8 shadow-modal-lg">
        <h1 className="text-2xl font-semibold text-brand-dirty">Verify your email</h1>
        <p className="mt-2 text-sm leading-6 text-brand-muted">
          Open the link we sent before signing in. The link expires after 24 hours.
        </p>
        {message && (
          <div className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            {message}
          </div>
        )}
        {error && (
          <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
        <div className="mt-6">
          <label className="mb-1.5 block text-xs font-medium tracking-wide text-brand-muted">Email</label>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && resend()}
            autoComplete="email"
            placeholder="you@email.com"
            className="w-full rounded-xl border border-brand-glow/15 bg-brand-accent/25 px-4 py-3 text-sm text-brand-dirty placeholder:text-brand-muted/60 focus:border-brand-glow/60 focus:outline-none focus:ring-2 focus:ring-brand-glow/30"
          />
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={resend}
          className="mt-6 w-full rounded-xl bg-gradient-to-r from-brand-accent to-brand-bright py-3.5 text-sm font-semibold text-brand-dirty disabled:opacity-50"
        >
          {loading ? 'Sending…' : 'Resend verification link'}
        </button>
        <p className="mt-5 text-center text-sm text-brand-muted">
          <Link to="/" className="text-brand-glow hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
