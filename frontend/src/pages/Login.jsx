import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { apiFetch, primeCsrf, markLoginSession, checkAuth } from '../api';

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

function BudgetVisual() {
  return (
    <div className="relative mx-auto mb-5 h-[198px] w-[240px]">
      <div className="login-orbit absolute left-1/2 top-1/2 h-[180px] w-[180px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/[0.06]" />
      <div className="login-orbit login-orbit-reverse absolute left-1/2 top-1/2 h-[142px] w-[142px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-brand-glow/10" />

      <div className="login-float-card login-float-1 absolute left-0 top-0 z-10 w-[144px] rounded-2xl border border-white/10 bg-white/[0.07] p-4 shadow-lg backdrop-blur-md">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-medium uppercase tracking-wider text-brand-muted">Allowance</span>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
        </div>
        <p className="text-xl font-semibold tracking-tight text-brand-dirty">₱2,500</p>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10">
          <div className="login-bar-fill h-full rounded-full bg-gradient-to-r from-brand-glow to-brand-bright" />
        </div>
        <p className="mt-1.5 text-[10px] text-brand-muted">38% used this week</p>
      </div>

      <div className="login-float-card login-float-2 absolute right-0 top-[68px] z-20 w-[148px] rounded-2xl border border-white/10 bg-white/[0.07] p-3.5 shadow-lg backdrop-blur-md">
        <span className="text-[10px] font-medium uppercase tracking-wider text-brand-muted">Today</span>
        <p className="mt-0.5 text-lg font-semibold text-brand-dirty">₱187</p>
        <div className="mt-2.5 space-y-1">
          {[
            { l: 'Fare', v: '₱45', c: 'bg-violet-400' },
            { l: 'Food', v: '₱120', c: 'bg-fuchsia-400' },
            { l: 'Other', v: '₱22', c: 'bg-purple-400' },
          ].map(({ l, v, c }) => (
            <div key={l} className="flex items-center justify-between text-[10px]">
              <span className="flex items-center gap-1.5 text-brand-muted">
                <span className={`h-1 w-1 rounded-full ${c}`} />{l}
              </span>
              <span className="text-brand-dirty/80">{v}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="login-float-card login-float-3 absolute right-1 top-0 z-30 flex h-[58px] w-[58px] flex-col items-center justify-center rounded-full border border-brand-glow/25 bg-brand-accent/70 shadow-[0_0_30px_rgba(157,78,221,0.3)] backdrop-blur-sm">
        <span className="text-base font-bold leading-none text-brand-dirty">62%</span>
        <span className="mt-0.5 text-[8px] uppercase tracking-widest text-brand-muted">left</span>
      </div>
    </div>
  );
}

function WelcomePanel({ isLogin, onSwitch }) {
  return (
    <div className="login-panel-visual relative flex h-full min-h-[280px] flex-col items-center justify-between overflow-hidden px-8 py-8 text-center lg:min-h-[480px] lg:px-12 lg:py-10">
      <div className="login-flame pointer-events-none absolute inset-0">
        <span className="login-flame-layer login-flame-1" />
        <span className="login-flame-layer login-flame-2" />
        <span className="login-flame-layer login-flame-3" />
      </div>
      <div className="login-orb login-orb-1" />
      <div className="login-orb login-orb-2" />
      <div className="login-orb login-orb-3" />

      <div className="relative z-10 flex items-center gap-3 self-end">
        <div className="text-right">
          <p className="text-[15px] font-semibold leading-tight tracking-tight text-brand-dirty">Budget Tracker</p>
          <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-brand-muted/80">Weekly expense manager</p>
        </div>
      </div>

      <div className="relative z-10 flex flex-1 flex-col items-center justify-center pt-4">
        <BudgetVisual />
        <div key={isLogin ? 'login' : 'register'} className="login-welcome-content">
          <h2 className="text-2xl font-semibold tracking-tight text-brand-dirty lg:text-[1.75rem]">
            {isLogin ? 'Welcome back' : 'Start tracking'}
          </h2>
          <p className="mt-3 max-w-[280px] text-sm leading-relaxed text-brand-muted">
            {isLogin
              ? 'Log items, auto-categorize spending, and keep your weekly budget on track.'
              : 'Set your allowance, add expenses as you go, and watch your savings grow.'}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={onSwitch}
        className="relative z-10 mt-6 rounded-full border border-brand-dirty/20 bg-white/[0.04] px-8 py-2.5 text-sm font-medium text-brand-dirty backdrop-blur-sm transition hover:border-brand-glow/40 hover:bg-white/[0.08] hover:shadow-[0_0_20px_rgba(157,78,221,0.15)]"
      >
        {isLogin ? 'No account yet? Sign up' : 'Already have one? Sign in'}
      </button>
    </div>
  );
}

function FormShell({ children, edge = 'right' }) {
  return (
    <div className="login-form-bg relative flex h-full min-h-[360px] flex-col justify-center px-8 py-8 sm:px-12 lg:min-h-[480px]">
      {edge === 'right' && (
        <div className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-brand-glow/20 to-transparent" />
      )}
      {edge === 'left' && (
        <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-brand-glow/20 to-transparent" />
      )}
      <div className="relative z-10 mx-auto w-full max-w-[340px]">{children}</div>
    </div>
  );
}

function SubmitButton({ loading, onClick, children }) {
  return (
    <button
      type="button"
      disabled={loading}
      onClick={onClick}
      className="group relative mt-7 w-full overflow-hidden rounded-xl bg-gradient-to-r from-brand-accent to-brand-bright py-3.5 text-sm font-semibold text-brand-dirty shadow-[0_4px_20px_rgba(123,44,191,0.35)] transition hover:shadow-[0_6px_28px_rgba(123,44,191,0.45)] hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
    >
      <span className="relative z-10 flex items-center justify-center gap-2">
        {loading && <span className="login-spinner h-4 w-4 rounded-full border-2 border-brand-dirty/30 border-t-brand-dirty" />}
        {children}
      </span>
      <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
    </button>
  );
}

function LoginForm({ onSubmit, loading, error }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const submit = () => onSubmit({ username, password, rememberMe });

  return (
    <div className="login-panel-content">
      <h2 className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-brand-dirty">Sign in</h2>
      <p className="mt-2 text-[13px] leading-relaxed text-brand-muted">Enter your credentials to continue</p>
      {error && (
        <div className="mt-5 animate-[shake_0.4s_ease] rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
      )}
      <div className="mt-7 space-y-4">
        <Field label="Username" value={username} onChange={(e) => setUsername(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} autoComplete="username" placeholder="your username" />
        <Field label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} autoComplete="current-password" placeholder="••••••••" />
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-brand-muted select-none">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-brand-glow/30 bg-brand-accent/40 text-brand-glow focus:ring-brand-glow/40"
          />
          Remember me
        </label>
        <Link to="/forgot-password" className="text-xs text-brand-glow hover:underline">Forgot password?</Link>
      </div>
      <SubmitButton loading={loading} onClick={submit}>{loading ? 'Signing in…' : 'Sign in'}</SubmitButton>
    </div>
  );
}

function RegisterForm({ onSubmit, loading, error }) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const submit = () => onSubmit({ username, email, password });

  return (
    <div className="login-panel-content">
      <h2 className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-brand-dirty">Sign up</h2>
      <p className="mt-2 text-[13px] leading-relaxed text-brand-muted">It only takes a minute</p>
      {error && (
        <div className="mt-4 animate-[shake_0.4s_ease] rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
      )}
      <div className="mt-6 space-y-3.5">
        <Field label="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" placeholder="min 5 characters" />
        <Field label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@email.com" />
        <Field label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} autoComplete="new-password" placeholder="••••••••" />
      </div>
      <SubmitButton loading={loading} onClick={submit}>{loading ? 'Creating…' : 'Create account'}</SubmitButton>
    </div>
  );
}

export default function Login() {
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const navigate = useNavigate();
  const isLogin = mode === 'login';

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (!localStorage.getItem('darkMode')) localStorage.setItem('darkMode', 'true');
    primeCsrf();
  }, []);

  useEffect(() => {
    let cancelled = false;
    checkAuth()
      .then((d) => {
        if (cancelled) return;
        if (d.authenticated) {
          navigate('/dashboard', { replace: true });
          return;
        }
        setAuthChecking(false);
      })
      .catch(() => {
        if (!cancelled) setAuthChecking(false);
      });
    return () => { cancelled = true; };
  }, [navigate]);

  const handleLogin = async ({ username, password, rememberMe }) => {
    setError('');
    if (!username || !password) return setError('Please enter username and password');
    setLoading(true);
    try {
      const res = await apiFetch('/api/login', {
        method: 'POST',
        body: JSON.stringify({ username, password, remember_me: Boolean(rememberMe) }),
      });
      const data = await res.json();
      if (res.ok) {
        markLoginSession(Boolean(rememberMe));
        navigate('/dashboard', { replace: true });
      } else setError(data.error || 'Login failed');
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async ({ username, email, password }) => {
    setError('');
    if (!username || !email || !password) return setError('Please fill in all fields');
    setLoading(true);
    try {
      const res = await apiFetch('/api/register', { method: 'POST', body: JSON.stringify({ username, email, password }) });
      const data = await res.json();
      if (res.ok) {
        markLoginSession(false);
        navigate('/dashboard', { replace: true });
      } else setError(data.error || 'Registration failed');
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setError('');
    setMode((m) => (m === 'login' ? 'register' : 'login'));
  };

  if (authChecking) {
    return (
      <div className="login-page flex min-h-[calc(100vh-32px)] items-center justify-center px-3 py-4">
        <p className="text-sm text-brand-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="login-page flex min-h-[calc(100vh-32px)] items-center justify-center px-3 py-4">
      <div className="login-modal-enter w-full max-w-[840px] overflow-hidden rounded-3xl border border-brand-glow/10 shadow-modal-lg">
        <div className="login-split relative hidden min-h-[480px] lg:block">
          <div className="grid h-full grid-cols-2">
            <FormShell edge="right">
              <div key={`login-${mode}`} className={isLogin ? 'login-reveal' : ''}>
                <LoginForm onSubmit={handleLogin} loading={loading} error={isLogin ? error : ''} />
              </div>
            </FormShell>
            <FormShell edge="left">
              <div key={`register-${mode}`} className={!isLogin ? 'login-reveal' : ''}>
                <RegisterForm onSubmit={handleRegister} loading={loading} error={!isLogin ? error : ''} />
              </div>
            </FormShell>
          </div>
          <div className={`login-overlay ${isLogin ? '' : 'login-overlay--register'}`}>
            <WelcomePanel isLogin={isLogin} onSwitch={switchMode} />
          </div>
        </div>

        <div className="lg:hidden">
          <div key={isLogin ? 'login' : 'register'} className="login-welcome-content">
            <FormShell edge="right">
              {isLogin ? (
                <LoginForm onSubmit={handleLogin} loading={loading} error={error} />
              ) : (
                <RegisterForm onSubmit={handleRegister} loading={loading} error={error} />
              )}
            </FormShell>
          </div>
          <button
            type="button"
            onClick={switchMode}
            className="block w-full bg-gradient-to-r from-brand-accent to-brand-bright py-4 text-center text-sm font-medium text-brand-dirty transition hover:brightness-110"
          >
            {isLogin ? 'No account yet? Sign up' : 'Already have one? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
}
