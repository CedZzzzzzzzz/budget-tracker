import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { apiFetch, parseApiResponse } from '../api';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const requested = useRef(false);
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('Verifying your email…');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (requested.current) return;
    requested.current = true;
    const token = searchParams.get('token') || '';
    navigate('/verify-email', { replace: true });
    if (!token) {
      setStatus('error');
      setMessage('This verification link is invalid or has expired.');
      return;
    }

    apiFetch('/api/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    })
      .then(parseApiResponse)
      .then(({ data, ok }) => {
        if (ok) {
          setStatus('success');
          setMessage(data.message || 'Email verified. You can sign in now.');
        } else {
          setStatus('error');
          setMessage(data.error || 'This verification link is invalid or has expired.');
        }
      })
      .catch(() => {
        setStatus('error');
        setMessage('Could not reach the server. Try opening the link again.');
      });
  }, [navigate, searchParams]);

  return (
    <div className="login-page flex min-h-[calc(100vh-32px)] items-center justify-center px-3 py-4">
      <div className="login-modal-enter w-full max-w-md rounded-3xl border border-brand-glow/10 bg-brand-accent/20 p-8 text-center shadow-modal-lg">
        <div
          className={`mx-auto flex h-12 w-12 items-center justify-center rounded-full text-xl font-semibold ${
            status === 'success'
              ? 'bg-emerald-500/15 text-emerald-300'
              : status === 'error'
                ? 'bg-red-500/15 text-red-300'
                : 'bg-brand-glow/15 text-brand-glow'
          }`}
          aria-hidden="true"
        >
          {status === 'success' ? '✓' : status === 'error' ? '!' : '…'}
        </div>
        <h1 className="mt-5 text-2xl font-semibold text-brand-dirty">
          {status === 'loading' ? 'Verifying email' : status === 'success' ? 'Email verified' : 'Verification failed'}
        </h1>
        <p className="mt-3 text-sm leading-6 text-brand-muted" role="status">{message}</p>
        {status === 'success' ? (
          <Link
            to="/"
            className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-brand-accent to-brand-bright py-3.5 text-sm font-semibold text-brand-dirty"
          >
            Continue to sign in
          </Link>
        ) : status === 'error' ? (
          <Link to="/verify-email-sent" className="mt-6 inline-block text-sm text-brand-glow hover:underline">
            Request another verification link
          </Link>
        ) : null}
      </div>
    </div>
  );
}
