import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiFetch } from '../api';
import { NAV_ITEMS } from '../utils/nav';
import { btnGhost, btnPrimary } from '../utils/theme';

const PAGE_BLURBS = {
  weekly: 'Set your weekly allowance, pick a day, and log expenses with categories, notes, and tags.',
  monthly: 'Review the month at a glance — total spent, saved, and week-by-week breakdowns.',
  reports: 'Build custom date-range or yearly summaries, then export CSV or PDF.',
  savings: 'Track closed-week savings, overspending, and goals toward a target amount.',
  budget: 'Set per-category weekly limits and recurring items like rent or subscriptions.',
  settings: 'Update your username, email, or password anytime.',
};

export const ONBOARDING_STEPS = NAV_ITEMS.map((item) => ({
  id: item.id,
  path: item.path,
  label: item.label,
  title: item.title,
  body: PAGE_BLURBS[item.id] || item.subtitle,
}));

function stepIndexForPath(pathname) {
  if (pathname === '/dashboard/monthly') {
    return ONBOARDING_STEPS.findIndex((s) => s.id === 'monthly');
  }
  const idx = ONBOARDING_STEPS.findIndex((s) => {
    if (s.id === 'weekly') return pathname === '/dashboard' || pathname === '/dashboard/';
    return pathname === s.path || pathname.startsWith(`${s.path}/`);
  });
  return idx >= 0 ? idx : 0;
}

export default function OnboardingTour({ username, onComplete }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const step = useMemo(
    () => Math.max(0, stepIndexForPath(location.pathname)),
    [location.pathname],
  );
  const current = ONBOARDING_STEPS[step];
  const isFirst = step === 0;
  const isLast = step === ONBOARDING_STEPS.length - 1;
  const progress = ((step + 1) / ONBOARDING_STEPS.length) * 100;

  useEffect(() => {
    const known = ONBOARDING_STEPS.some((s) => {
      if (s.id === 'weekly') return location.pathname === '/dashboard' || location.pathname === '/dashboard/';
      if (s.id === 'monthly') return location.pathname === '/dashboard/monthly';
      return location.pathname === s.path || location.pathname.startsWith(`${s.path}/`);
    });
    if (!known) navigate(ONBOARDING_STEPS[0].path, { replace: true });
  }, [location.pathname, navigate]);

  const goTo = (index) => {
    const next = ONBOARDING_STEPS[Math.max(0, Math.min(ONBOARDING_STEPS.length - 1, index))];
    if (next) navigate(next.path);
  };

  const finish = async () => {
    setLoading(true);
    setError('');
    try {
      const r = await apiFetch('/api/onboarding/complete', {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(data.error || 'Could not finish onboarding');
        return;
      }
      onComplete?.();
      navigate('/dashboard', { replace: true });
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  if (!current) return null;

  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[1200] p-3 sm:p-5">
      <div className="pointer-events-auto mx-auto w-full max-w-xl rounded-2xl border border-purple-primary/25 bg-[rgba(18,12,28,0.92)] p-4 shadow-[0_20px_60px_rgba(0,0,0,0.45)] backdrop-blur-xl sm:p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-purple-muted">
            Tour · {step + 1}/{ONBOARDING_STEPS.length}
          </p>
          <button
            type="button"
            className="text-xs text-purple-muted transition hover:text-purple-text"
            onClick={finish}
            disabled={loading}
          >
            Skip tour
          </button>
        </div>

        <div className="glass-track mb-4 h-1 overflow-hidden rounded-full">
          <div
            className="h-full rounded-full bg-gradient-to-r from-purple-primary to-purple-primary-light transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        <p className="text-xs font-medium text-purple-primary-light">
          {current.label}
          {isFirst && username ? ` · Hey ${username}` : ''}
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-purple-text">
          {current.title}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-purple-soft">
          {current.body}
        </p>

        {error && (
          <p className="mt-3 text-sm text-red-300">{error}</p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={btnGhost}
            onClick={() => goTo(step - 1)}
            disabled={isFirst || loading}
          >
            Back
          </button>
          <div className="ml-auto flex flex-wrap gap-2">
            {!isLast ? (
              <button
                type="button"
                className={btnPrimary}
                onClick={() => goTo(step + 1)}
                disabled={loading}
              >
                Next page
              </button>
            ) : (
              <button
                type="button"
                className={btnPrimary}
                onClick={finish}
                disabled={loading}
              >
                {loading ? 'Finishing…' : 'Done'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
