import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { apiFetch, parseApiResponse } from '../api';
import {
  adminGlassControl as control,
  adminGlassInset as inset,
  adminGlassPanel as glassPanel,
} from '../utils/adminGlass';

const panel = glassPanel;
const analyticsPanel = glassPanel;

const iconProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  className: 'h-5 w-5',
};

function UsersIcon() {
  return <svg {...iconProps}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>;
}

function CheckIcon() {
  return <svg {...iconProps}><path d="M20 6 9 17l-5-5" /></svg>;
}

function ShieldIcon() {
  return <svg {...iconProps}><path d="M12 3 4.5 6v5.2c0 4.7 3.2 8.2 7.5 9.8 4.3-1.6 7.5-5.1 7.5-9.8V6L12 3Z" /><path d="m9 12 2 2 4-4" /></svg>;
}

function SearchIcon() {
  return <svg {...iconProps}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>;
}

function RefreshIcon() {
  return <svg {...iconProps}><path d="M20 6v5h-5" /><path d="M4 18v-5h5" /><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11M5.5 15A7 7 0 0 0 18 17.5l2-4.5" /></svg>;
}

function BellIcon() {
  return <svg {...iconProps}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></svg>;
}

function CloseIcon() {
  return <svg {...iconProps}><path d="m18 6-12 12M6 6l12 12" /></svg>;
}

function EyeIcon() {
  return <svg {...iconProps}><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></svg>;
}

function MailIcon() {
  return <svg {...iconProps}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>;
}

function KeyIcon() {
  return <svg {...iconProps}><circle cx="8" cy="15" r="4" /><path d="m11 12 8-8M16 7l2 2M14 9l2 2" /></svg>;
}

function SignOutIcon() {
  return <svg {...iconProps}><path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-6" /></svg>;
}

const ACTION_CONFIG = {
  suspend: {
    title: 'Suspend account',
    description: 'Block this account from signing in. Financial records remain unchanged.',
    tone: 'danger',
  },
  reactivate: {
    title: 'Reactivate account',
    description: 'Restore account access without changing verification or financial records.',
    tone: 'success',
  },
  'resend-verification': {
    title: 'Resend verification email',
    description: 'Invalidate older verification links and send a new one to the registered address.',
    tone: 'primary',
  },
  'send-password-reset': {
    title: 'Send password-reset email',
    description: 'Send a one-time reset link. You will never see the token or choose the new password.',
    tone: 'primary',
  },
  'revoke-sessions': {
    title: 'Force sign-out',
    description: 'Revoke every existing session for this account. The user must sign in again.',
    tone: 'warning',
  },
};

const AUDIT_ACTION_LABELS = {
  grant_admin: 'Granted admin access',
  revoke_admin: 'Revoked admin access',
  suspend_user: 'Suspended account',
  reactivate_user: 'Reactivated account',
  resend_verification: 'Resent verification email',
  send_password_reset: 'Sent password-reset email',
  revoke_sessions: 'Revoked sessions',
};

const SECURITY_EVENT_LABELS = {
  login_success: 'Successful sign-in',
  login_failed: 'Failed sign-in',
  password_reset_completed: 'Password reset completed',
  password_changed: 'Password changed',
  sessions_revoked: 'Sessions revoked',
  email_verification: 'Verification email',
  password_reset: 'Password-reset email',
  suspend_user: 'Account suspended',
  reactivate_user: 'Account reactivated',
  resend_verification: 'Verification email requested',
  send_password_reset: 'Password reset requested',
  revoke_sessions: 'Sessions revoked by admin',
  grant_admin: 'Admin access granted',
  revoke_admin: 'Admin access revoked',
};

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toLocaleString();
}

function formatDate(value, fallback = 'Never') {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function AccountPulseCard({ metrics }) {
  const newUsers = Number(metrics?.new_users_30d || 0);
  const recentUsers = Number(metrics?.new_users_7d || 0);

  return (
    <article className={`${analyticsPanel} min-h-64 p-5 sm:p-6`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-purple-muted">Account pulse</p>
        <span className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-purple-soft">Last 30 days</span>
      </div>
      <div className="mt-8">
        <p className="text-4xl font-semibold tracking-tight text-purple-text">{formatNumber(newUsers)}</p>
        <h3 className="mt-2 text-base font-medium text-purple-text">New accounts</h3>
        <p className="mt-2 text-sm leading-6 text-purple-muted">Registration activity across the platform.</p>
      </div>
      <div className="mt-7 grid grid-cols-2 border-t border-white/8 pt-5">
        <div>
          <p className="text-xs text-purple-muted">Joined in 7 days</p>
          <p className="mt-1.5 text-lg font-semibold text-purple-text">{formatNumber(recentUsers)}</p>
        </div>
        <div className="border-l border-white/8 pl-5">
          <p className="text-xs text-purple-muted">Logged in 30 days</p>
          <p className="mt-1.5 text-lg font-semibold text-purple-text">{formatNumber(metrics?.logins_30d)}</p>
        </div>
      </div>
    </article>
  );
}

function AccountOverviewCard({ metrics }) {
  const activeUsers = Number(metrics?.active_users || 0);
  const suspendedUsers = Number(metrics?.suspended_users || 0);
  const newUsers = Number(metrics?.new_users_30d || 0);
  const recentUsers = Number(metrics?.new_users_7d || 0);
  const chartMaximum = Math.max(newUsers, recentUsers, 1);
  const recentWidth = recentUsers ? Math.max(8, Math.round((recentUsers / chartMaximum) * 100)) : 0;
  const monthlyWidth = newUsers ? Math.max(8, Math.round((newUsers / chartMaximum) * 100)) : 0;

  return (
    <article className={`${analyticsPanel} min-h-64 p-5 sm:p-6`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-purple-muted">Account overview</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-purple-text">{formatNumber(metrics?.total_users)}</p>
          <p className="mt-1 text-xs text-purple-soft">Total registered accounts</p>
        </div>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-purple-primary/20 bg-purple-primary/15 text-purple-primary-light">
          <UsersIcon />
        </span>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <span className="rounded-lg border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300">{formatNumber(activeUsers)} active</span>
        <span className="rounded-lg border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-300">{formatNumber(suspendedUsers)} suspended</span>
      </div>
      <div className="mt-6 space-y-3 border-t border-white/8 pt-5">
        <div className="grid grid-cols-[76px_1fr_auto] items-center gap-3 text-xs">
          <span className="text-purple-muted">Last 7 days</span>
          <span className="h-2 overflow-hidden rounded-full bg-black/20"><span className="block h-full rounded-full bg-purple-primary" style={{ width: `${recentWidth}%` }} /></span>
          <span className="font-semibold text-purple-text">{formatNumber(recentUsers)}</span>
        </div>
        <div className="grid grid-cols-[76px_1fr_auto] items-center gap-3 text-xs">
          <span className="text-purple-muted">Last 30 days</span>
          <span className="h-2 overflow-hidden rounded-full bg-black/20"><span className="block h-full rounded-full bg-purple-primary-light" style={{ width: `${monthlyWidth}%` }} /></span>
          <span className="font-semibold text-purple-text">{formatNumber(newUsers)}</span>
        </div>
      </div>
    </article>
  );
}

function ActiveCoverageCard({ metrics, rate }) {
  return (
    <article className={`${analyticsPanel} min-h-64 p-5 sm:p-6`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-purple-muted">Active coverage</p>
          <p className="mt-2 text-sm text-purple-soft">Accounts currently allowed to sign in</p>
        </div>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-purple-primary-light/20 bg-purple-primary/15 text-purple-primary-light">
          <CheckIcon />
        </span>
      </div>
      <div className="relative mx-auto mt-3 h-36 w-36">
        <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle cx="60" cy="60" r="48" pathLength="100" fill="none" stroke="currentColor" strokeWidth="13" className="text-white/8" />
          <circle cx="60" cy="60" r="48" pathLength="100" fill="none" stroke="url(#active-coverage-gradient)" strokeWidth="13" strokeLinecap="round" strokeDasharray={`${rate} ${100 - rate}`} />
          <defs>
            <linearGradient id="active-coverage-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#b982ff" />
              <stop offset="100%" stopColor="#8b3ce0" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold text-purple-text">{rate}%</span>
          <span className="mt-1 text-[11px] uppercase tracking-[0.14em] text-purple-muted">Active</span>
        </div>
      </div>
      <div className="mx-auto mt-2 grid max-w-64 grid-cols-2 divide-x divide-white/8 rounded-xl border border-white/8 text-center text-xs">
        <span className="px-3 py-2.5 text-purple-soft"><strong className="mr-1 font-semibold text-purple-text">{formatNumber(metrics?.active_users)}</strong> active</span>
        <span className="px-3 py-2.5 text-purple-soft"><strong className="mr-1 font-semibold text-purple-text">{formatNumber(metrics?.suspended_users)}</strong> suspended</span>
      </div>
    </article>
  );
}

function SystemHealthPanel({ health, loading }) {
  const email = health?.email || {};
  const authentication = health?.authentication || {};
  const emailHealthy = email.configured && Number(email.failed_24h || 0) === 0;

  return (
    <section className={`${panel} p-5 sm:p-6`} aria-labelledby="admin-system-health">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="admin-system-health" className="text-lg font-semibold text-purple-text">System health</h2>
          <p className="mt-1 text-sm text-purple-muted">Email and authentication signals from the last 24 hours.</p>
        </div>
        <p className="text-xs text-purple-muted">{loading ? 'Refreshing…' : `Checked ${formatDate(health?.checked_at, 'Not checked')}`}</p>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <article className={`${inset} min-w-0 p-4 sm:p-5`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-purple-primary-light/20 bg-purple-primary/15 text-purple-primary-light">
                <MailIcon />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-purple-text">Email delivery</p>
                <p className="mt-0.5 break-words text-xs capitalize text-purple-muted">
                  {email.transport ? email.transport.replaceAll('_', ' ') : 'Unknown transport'}
                </p>
              </div>
            </div>
            <span className={`w-fit shrink-0 whitespace-nowrap rounded-lg border px-2.5 py-1 text-xs font-medium ${emailHealthy ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-300' : 'border-amber-400/20 bg-amber-500/10 text-amber-300'}`}>
              {email.configured ? (emailHealthy ? 'Operational' : 'Needs review') : 'Not configured'}
            </span>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center">
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(email.sent_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Sent</p></div>
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(email.queued_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Queued</p></div>
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(email.failed_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Failed</p></div>
          </div>
          <div className="mt-4 flex flex-col gap-1 border-t border-white/10 pt-3 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <span className="text-purple-muted">Last delivery</span>
            <span className="break-words font-medium text-purple-soft sm:text-right">{formatDate(email.last_delivery_at)}</span>
          </div>
        </article>
        <article className={`${inset} min-w-0 p-4 sm:p-5`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-purple-primary-light/20 bg-purple-primary/15 text-purple-primary-light">
                <ShieldIcon />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-purple-text">Authentication</p>
                <p className="mt-0.5 text-xs text-purple-muted">Security activity</p>
              </div>
            </div>
            <span className="w-fit shrink-0 whitespace-nowrap rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-purple-soft">
              Last 24 hours
            </span>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center">
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(authentication.login_success_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Sign-ins</p></div>
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(authentication.login_failed_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Failed</p></div>
            <div className="min-w-0 rounded-xl border border-white/10 bg-black/10 px-2 py-3"><p className="truncate text-lg font-semibold text-purple-text">{formatNumber(authentication.sessions_revoked_24h)}</p><p className="mt-0.5 text-[11px] text-purple-muted">Revoked</p></div>
          </div>
          <div className="mt-4 flex flex-col gap-1 border-t border-white/10 pt-3 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <span className="text-purple-muted">Data scope</span>
            <span className="font-medium text-purple-soft sm:text-right">Authentication metadata only</span>
          </div>
        </article>
      </div>
    </section>
  );
}

function StatusBadge({ status }) {
  const suspended = status === 'suspended';
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${suspended
      ? 'border-red-400/25 bg-red-500/10 text-red-300'
      : 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300'}`}>
      {suspended ? 'Suspended' : 'Active'}
    </span>
  );
}

function VerifiedBadge({ verified }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${verified
      ? 'border-purple-primary-light/25 bg-purple-primary/10 text-purple-primary-light'
      : 'border-amber-400/25 bg-amber-500/10 text-amber-300'}`}>
      {verified ? 'Verified' : 'Unverified'}
    </span>
  );
}

function UserAction({ user, onAction }) {
  const isAdmin = user.role === 'admin';
  const isSuspended = user.account_status === 'suspended';
  return (
    <button
      type="button"
      disabled={isAdmin}
      onClick={() => onAction(user, isSuspended ? 'reactivate' : 'suspend')}
      className={`min-h-10 rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-35 ${isSuspended
        ? 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
        : 'border-red-400/25 bg-red-500/10 text-red-300 hover:bg-red-500/20'}`}
    >
      {isAdmin ? 'Protected' : isSuspended ? 'Reactivate' : 'Suspend'}
    </button>
  );
}

function ViewUserButton({ user, onView }) {
  return (
    <button type="button" onClick={() => onView(user)} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-purple-text transition hover:bg-white/5">
      <EyeIcon />
      View
    </button>
  );
}

function EmptyState({ children }) {
  return (
    <div className="flex min-h-40 items-center justify-center px-6 text-center text-sm text-purple-muted">
      {children}
    </div>
  );
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { isAdmin, username } = useOutletContext();
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);
  const [users, setUsers] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [auditPagination, setAuditPagination] = useState({ page: 1, pages: 1, total: 0, page_size: 20 });
  const [auditPage, setAuditPage] = useState(1);
  const [auditSearchDraft, setAuditSearchDraft] = useState('');
  const [auditQuery, setAuditQuery] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [auditOutcome, setAuditOutcome] = useState('');
  const [auditSource, setAuditSource] = useState('');
  const [auditDateFrom, setAuditDateFrom] = useState('');
  const [auditDateTo, setAuditDateTo] = useState('');
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0, page_size: 20 });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchDraft, setSearchDraft] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [sort, setSort] = useState('created_at');
  const [direction, setDirection] = useState('desc');
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [healthLoading, setHealthLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(true);
  const [activityOpen, setActivityOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [action, setAction] = useState(null);
  const [reason, setReason] = useState('');
  const [password, setPassword] = useState('');
  const [actionError, setActionError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const modalRef = useRef(null);
  const passwordRef = useRef(null);
  const actionTriggerRef = useRef(null);
  const activityPanelRef = useRef(null);
  const activityTriggerRef = useRef(null);
  const detailPanelRef = useRef(null);
  const detailTriggerRef = useRef(null);

  useEffect(() => {
    if (!isAdmin) navigate('/dashboard', { replace: true });
  }, [isAdmin, navigate]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchDraft.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchDraft]);

  const handleForbidden = useCallback((status) => {
    if (status === 401) navigate('/', { replace: true });
    if (status === 403 || status === 404) navigate('/dashboard', { replace: true });
  }, [navigate]);

  const loadOverview = useCallback(async () => {
    if (!isAdmin) return;
    setOverviewLoading(true);
    try {
      const response = await apiFetch('/api/admin/overview');
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        handleForbidden(status);
        throw new Error(data.error || 'Could not load admin metrics.');
      }
      setMetrics(data.metrics || {});
    } catch (requestError) {
      setError(requestError.message || 'Could not load admin metrics.');
    } finally {
      setOverviewLoading(false);
    }
  }, [handleForbidden, isAdmin]);

  const loadHealth = useCallback(async () => {
    if (!isAdmin) return;
    setHealthLoading(true);
    try {
      const response = await apiFetch('/api/admin/system-health');
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        handleForbidden(status);
        throw new Error(data.error || 'Could not load system health.');
      }
      setHealth(data.health || {});
    } catch (requestError) {
      setError(requestError.message || 'Could not load system health.');
    } finally {
      setHealthLoading(false);
    }
  }, [handleForbidden, isAdmin]);

  const loadUsers = useCallback(async () => {
    if (!isAdmin) return;
    setUsersLoading(true);
    setError('');
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort,
      direction,
    });
    if (query) params.set('q', query);
    if (statusFilter) params.set('status', statusFilter);
    if (roleFilter) params.set('role', roleFilter);
    try {
      const response = await apiFetch(`/api/admin/users?${params}`);
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        handleForbidden(status);
        throw new Error(data.error || 'Could not load accounts.');
      }
      setUsers(data.users || []);
      setPagination(data.pagination || { page: 1, pages: 1, total: 0, page_size: pageSize });
    } catch (requestError) {
      setUsers([]);
      setError(requestError.message || 'Could not load accounts.');
    } finally {
      setUsersLoading(false);
    }
  }, [direction, handleForbidden, isAdmin, page, pageSize, query, roleFilter, sort, statusFilter]);

  const loadAudit = useCallback(async () => {
    if (!isAdmin) return;
    setAuditLoading(true);
    const params = new URLSearchParams({
      page: String(auditPage),
      page_size: '20',
    });
    if (auditQuery) params.set('q', auditQuery);
    if (auditAction) params.set('action', auditAction);
    if (auditOutcome) params.set('outcome', auditOutcome);
    if (auditSource) params.set('source', auditSource);
    if (auditDateFrom) params.set('date_from', auditDateFrom);
    if (auditDateTo) params.set('date_to', auditDateTo);
    try {
      const response = await apiFetch(`/api/admin/audit-events?${params}`);
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        handleForbidden(status);
        throw new Error(data.error || 'Could not load audit activity.');
      }
      setAuditEvents(data.events || []);
      setAuditPagination(data.pagination || { page: 1, pages: 1, total: 0, page_size: 20 });
    } catch {
      setAuditEvents([]);
      setAuditPagination({ page: 1, pages: 1, total: 0, page_size: 20 });
    } finally {
      setAuditLoading(false);
    }
  }, [auditAction, auditDateFrom, auditDateTo, auditOutcome, auditPage, auditQuery, auditSource, handleForbidden, isAdmin]);

  const loadUserDetail = useCallback(async (userId) => {
    if (!isAdmin || !userId) return;
    setDetailLoading(true);
    try {
      const response = await apiFetch(`/api/admin/users/${userId}`);
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        if (status === 401 || status === 403) handleForbidden(status);
        throw new Error(data.error || 'Could not load account details.');
      }
      setSelectedUser(data.user || null);
      setSecurityEvents(data.security_events || []);
    } catch (requestError) {
      setError(requestError.message || 'Could not load account details.');
    } finally {
      setDetailLoading(false);
    }
  }, [handleForbidden, isAdmin]);

  useEffect(() => { loadOverview(); }, [loadOverview]);
  useEffect(() => { loadHealth(); }, [loadHealth]);
  useEffect(() => { loadUsers(); }, [loadUsers]);
  useEffect(() => { loadAudit(); }, [loadAudit]);

  const verificationRate = useMemo(() => {
    if (!metrics?.total_users) return 0;
    return Math.round((metrics.verified_users / metrics.total_users) * 100);
  }, [metrics]);

  const activeRate = useMemo(() => {
    if (!metrics?.total_users) return 0;
    return Math.round((metrics.active_users / metrics.total_users) * 100);
  }, [metrics]);

  const closeActivity = useCallback(() => {
    setActivityOpen(false);
    requestAnimationFrame(() => activityTriggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!activityOpen) return undefined;
    requestAnimationFrame(() => activityPanelRef.current?.querySelector('button')?.focus());
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeActivity();
      }
      if (event.key !== 'Tab' || !activityPanelRef.current) return;
      const focusable = [...activityPanelRef.current.querySelectorAll('button:not([disabled])')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [activityOpen, closeActivity]);

  const closeDetail = useCallback(() => {
    setSelectedUser(null);
    setSecurityEvents([]);
    requestAnimationFrame(() => detailTriggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!selectedUser || action) return undefined;
    requestAnimationFrame(() => detailPanelRef.current?.querySelector('button')?.focus());
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeDetail();
      }
      if (event.key !== 'Tab' || !detailPanelRef.current) return;
      const focusable = [...detailPanelRef.current.querySelectorAll('button:not([disabled])')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [action, closeDetail, selectedUser]);

  const closeAction = useCallback(() => {
    if (submitting) return;
    setAction(null);
    setReason('');
    setPassword('');
    setActionError('');
    requestAnimationFrame(() => actionTriggerRef.current?.focus());
  }, [submitting]);

  useEffect(() => {
    if (!action) return undefined;
    requestAnimationFrame(() => passwordRef.current?.focus());
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeAction();
      }
      if (event.key !== 'Tab' || !modalRef.current) return;
      const focusable = [...modalRef.current.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled])')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [action, closeAction]);

  const openAction = (user, type) => {
    actionTriggerRef.current = document.activeElement;
    setAction({ user, type });
    setReason('');
    setPassword('');
    setActionError('');
  };

  const openUserDetail = (user) => {
    detailTriggerRef.current = document.activeElement;
    setSelectedUser(user);
    setSecurityEvents([]);
    setNotice('');
    loadUserDetail(user.id);
  };

  const submitAction = async () => {
    if (!action || submitting) return;
    if (reason.trim().length < 5 || !password) {
      setActionError('Enter your current password and a reason of at least 5 characters.');
      return;
    }
    setSubmitting(true);
    setActionError('');
    const targetUserId = action.user.id;
    try {
      const response = await apiFetch(`/api/admin/users/${action.user.id}/${action.type}`, {
        method: 'POST',
        body: JSON.stringify({ current_password: password, reason: reason.trim() }),
      });
      const { data, ok, status } = await parseApiResponse(response);
      if (!ok) {
        handleForbidden(status === 401 && data.error?.includes('password') ? 0 : status);
        throw new Error(data.error || 'The administrative action could not be completed.');
      }
      setAction(null);
      setReason('');
      setPassword('');
      setNotice(data.message || `${ACTION_CONFIG[action.type]?.title || 'Administrative action'} completed.`);
      await Promise.all([
        loadOverview(),
        loadHealth(),
        loadUsers(),
        loadAudit(),
        selectedUser?.id === targetUserId ? loadUserDetail(targetUserId) : Promise.resolve(),
      ]);
      requestAnimationFrame(() => actionTriggerRef.current?.focus());
    } catch (requestError) {
      setPassword('');
      setActionError(requestError.message || 'The administrative action could not be completed.');
      requestAnimationFrame(() => passwordRef.current?.focus());
    } finally {
      setSubmitting(false);
    }
  };

  const refreshAll = () => {
    setError('');
    loadOverview();
    loadHealth();
    loadUsers();
    loadAudit();
    if (selectedUser?.id) loadUserDetail(selectedUser.id);
  };

  const actionConfig = action ? ACTION_CONFIG[action.type] : null;
  const actionText = actionConfig?.title || 'Confirm action';
  const actionTitleClass = {
    danger: 'text-red-300',
    success: 'text-emerald-300',
    warning: 'text-amber-300',
    primary: 'text-purple-primary-light',
  }[actionConfig?.tone] || 'text-purple-text';
  const actionButtonClass = {
    danger: 'bg-red-600 hover:bg-red-500',
    success: 'bg-emerald-600 hover:bg-emerald-500',
    warning: 'bg-amber-600 hover:bg-amber-500',
    primary: 'bg-purple-primary hover:bg-purple-primary-light',
  }[actionConfig?.tone] || 'bg-purple-primary hover:bg-purple-primary-light';

  if (!isAdmin) return null;

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 sm:space-y-6">
      <section className={`${panel} relative overflow-hidden p-5 sm:p-6 lg:p-7`}>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(139,60,224,0.42),transparent_34%),radial-gradient(circle_at_90%_20%,rgba(185,130,255,0.18),transparent_30%)]" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-purple-primary-light/25 bg-purple-primary/20 text-purple-primary-light shadow-glow">
              <ShieldIcon />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-purple-primary-light">Operations overview</p>
              <h2 className="mt-1 text-xl font-semibold text-purple-text sm:text-2xl">Welcome back, {username || 'administrator'}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-purple-soft">
                Monitor account access and verification without opening anyone&apos;s financial records.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={refreshAll}
            disabled={overviewLoading || usersLoading}
            className="inline-flex min-h-11 items-center justify-center gap-2 self-stretch rounded-xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-purple-text transition hover:bg-white/10 disabled:opacity-50 sm:self-auto"
          >
            <RefreshIcon />
            Refresh
          </button>
        </div>
        <div className="relative mt-6 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <div className="mb-2 flex items-center justify-between text-xs text-purple-soft">
              <span>Email verification coverage</span>
              <span className="font-semibold text-purple-text">{verificationRate}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-black/20">
              <div className="h-full rounded-full bg-gradient-to-r from-purple-primary to-purple-primary-light transition-all duration-500" style={{ width: `${verificationRate}%` }} />
            </div>
          </div>
          <p className="text-xs text-purple-muted sm:text-right">
            {formatNumber(metrics?.verified_users)} of {formatNumber(metrics?.total_users)} accounts verified
          </p>
        </div>
      </section>

      {error && (
        <div role="alert" className="rounded-xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {notice && (
        <div role="status" className="flex items-center justify-between gap-3 rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice('')} className="rounded-lg px-2 py-1 text-xs font-semibold text-emerald-200 hover:bg-white/5">Dismiss</button>
        </div>
      )}

      <section aria-label="Account analytics" className="grid gap-4 lg:grid-cols-3">
        <AccountPulseCard metrics={metrics} />
        <AccountOverviewCard metrics={metrics} />
        <ActiveCoverageCard metrics={metrics} rate={activeRate} />
      </section>

      <SystemHealthPanel health={health} loading={healthLoading} />

      <section className={`${panel} min-w-0 overflow-hidden`}>
        <div className="border-b border-white/8 p-4 sm:p-5 lg:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-purple-text">User management</h2>
              <p className="mt-1 text-sm text-purple-muted">Search account metadata and manage access.</p>
            </div>
            <div className="flex items-center justify-between gap-3 sm:justify-end">
              <p className="text-xs text-purple-soft">{formatNumber(pagination.total)} matching accounts</p>
              <button
                ref={activityTriggerRef}
                type="button"
                onClick={() => setActivityOpen(true)}
                aria-label={`Open admin audit history${auditPagination.total ? `, ${auditPagination.total} events` : ''}`}
                className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-purple-primary-light transition hover:border-purple-primary/35 hover:bg-purple-primary/15"
              >
                <BellIcon />
                {auditPagination.total > 0 && (
                  <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full border-2 border-[#180731] bg-purple-primary px-1 text-[10px] font-bold text-white">
                    {auditPagination.total > 99 ? '99+' : auditPagination.total}
                  </span>
                )}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(240px,1.6fr)_minmax(140px,.7fr)_minmax(140px,.7fr)_minmax(160px,.8fr)_110px]">
            <label className="relative block sm:col-span-2 lg:col-span-1">
              <span className="sr-only">Search username or email</span>
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-purple-muted"><SearchIcon /></span>
              <input
                className={`${control} pl-11`}
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Search username or email"
                maxLength={100}
              />
            </label>
            <select className={control} value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} aria-label="Filter by status">
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
            <select className={control} value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value); setPage(1); }} aria-label="Filter by role">
              <option value="">All roles</option>
              <option value="user">Users</option>
              <option value="admin">Admins</option>
            </select>
            <select className={control} value={`${sort}:${direction}`} onChange={(event) => {
              const [nextSort, nextDirection] = event.target.value.split(':');
              setSort(nextSort);
              setDirection(nextDirection);
              setPage(1);
            }} aria-label="Sort accounts">
              <option value="created_at:desc">Newest first</option>
              <option value="created_at:asc">Oldest first</option>
              <option value="last_login_at:desc">Recent login</option>
              <option value="username:asc">Username A–Z</option>
              <option value="email:asc">Email A–Z</option>
            </select>
            <select className={control} value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} aria-label="Accounts per page">
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>

        {usersLoading ? (
          <EmptyState>Loading accounts…</EmptyState>
        ) : users.length === 0 ? (
          <EmptyState>No accounts match these filters.</EmptyState>
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-white/8 text-xs uppercase tracking-[0.12em] text-purple-muted">
                    <th className="px-5 py-4 font-semibold">Account</th>
                    <th className="px-4 py-4 font-semibold">Verification</th>
                    <th className="px-4 py-4 font-semibold">Last login</th>
                    <th className="px-4 py-4 font-semibold">Status</th>
                    <th className="px-4 py-4 font-semibold">Role</th>
                    <th className="px-5 py-4 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} className="border-b border-white/6 transition last:border-0 hover:bg-white/[0.025]">
                      <td className="px-5 py-4">
                        <p className="font-medium text-purple-text">{user.username}</p>
                        <p className="mt-1 max-w-64 truncate text-xs text-purple-muted" title={user.email}>{user.email}</p>
                        <p className="mt-1 text-[11px] text-purple-muted">Joined {formatDate(user.created_at)}</p>
                      </td>
                      <td className="px-4 py-4"><VerifiedBadge verified={user.email_verified} /></td>
                      <td className="px-4 py-4 text-sm text-purple-soft">{formatDate(user.last_login_at)}</td>
                      <td className="px-4 py-4"><StatusBadge status={user.account_status} /></td>
                      <td className="px-4 py-4 text-sm capitalize text-purple-soft">{user.role}</td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          <ViewUserButton user={user} onView={openUserDetail} />
                          <UserAction user={user} onAction={openAction} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="space-y-3 p-3 md:hidden">
              {users.map((user) => (
                <article key={user.id} className={`${inset} p-4`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-purple-text">{user.username}</p>
                      <p className="mt-1 truncate text-xs text-purple-muted">{user.email}</p>
                    </div>
                    <StatusBadge status={user.account_status} />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                    <div><p className="text-purple-muted">Verification</p><div className="mt-1.5"><VerifiedBadge verified={user.email_verified} /></div></div>
                    <div><p className="text-purple-muted">Role</p><p className="mt-2 font-medium capitalize text-purple-text">{user.role}</p></div>
                    <div><p className="text-purple-muted">Joined</p><p className="mt-1.5 leading-5 text-purple-soft">{formatDate(user.created_at)}</p></div>
                    <div><p className="text-purple-muted">Last login</p><p className="mt-1.5 leading-5 text-purple-soft">{formatDate(user.last_login_at)}</p></div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2 border-t border-white/8 pt-4">
                    <ViewUserButton user={user} onView={openUserDetail} />
                    <UserAction user={user} onAction={openAction} />
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        <div className="flex flex-col gap-3 border-t border-white/8 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <p className="text-xs text-purple-muted">Page {pagination.page} of {pagination.pages}</p>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <button type="button" disabled={page <= 1 || usersLoading} onClick={() => setPage((current) => Math.max(1, current - 1))} className="min-h-11 rounded-xl border border-white/10 px-4 text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:opacity-35">Previous</button>
            <button type="button" disabled={page >= pagination.pages || usersLoading} onClick={() => setPage((current) => Math.min(pagination.pages, current + 1))} className="min-h-11 rounded-xl border border-white/10 px-4 text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:opacity-35">Next</button>
          </div>
        </div>
      </section>

      {selectedUser && (
        <div className="fixed inset-0 z-40 flex items-end justify-end bg-black/65 backdrop-blur-sm sm:items-stretch" onMouseDown={(event) => event.target === event.currentTarget && closeDetail()}>
          <aside ref={detailPanelRef} role="dialog" aria-modal="true" aria-labelledby="admin-user-detail-title" className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-[#180731] shadow-2xl sm:max-h-none sm:max-w-xl sm:rounded-none sm:rounded-l-3xl">
            <div className="mx-auto mt-3 h-1 w-10 rounded-full bg-white/20 sm:hidden" />
            <div className="flex items-start justify-between gap-4 border-b border-white/8 p-5 sm:p-6">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-purple-muted">Account support</p>
                <h2 id="admin-user-detail-title" className="mt-1 truncate text-xl font-semibold text-purple-text">{selectedUser.username}</h2>
                <p className="mt-1 truncate text-sm text-purple-muted">{selectedUser.email}</p>
              </div>
              <button type="button" onClick={closeDetail} aria-label="Close account details" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 text-purple-soft transition hover:bg-white/5 hover:text-purple-text"><CloseIcon /></button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
              {detailLoading ? (
                <EmptyState>Loading account details…</EmptyState>
              ) : (
                <div className="space-y-6">
                  <section aria-labelledby="account-summary-title">
                    <div className="flex items-center justify-between gap-3">
                      <h3 id="account-summary-title" className="text-sm font-semibold text-purple-text">Account summary</h3>
                      <div className="flex gap-2"><VerifiedBadge verified={selectedUser.email_verified} /><StatusBadge status={selectedUser.account_status} /></div>
                    </div>
                    <dl className={`${inset} mt-3 grid grid-cols-2 gap-x-4 gap-y-5 p-4 text-sm`}>
                      <div><dt className="text-xs text-purple-muted">Role</dt><dd className="mt-1 capitalize text-purple-text">{selectedUser.role}</dd></div>
                      <div><dt className="text-xs text-purple-muted">Created</dt><dd className="mt-1 text-purple-text">{formatDate(selectedUser.created_at)}</dd></div>
                      <div><dt className="text-xs text-purple-muted">Last login</dt><dd className="mt-1 text-purple-text">{formatDate(selectedUser.last_login_at)}</dd></div>
                      <div><dt className="text-xs text-purple-muted">Last forced sign-out</dt><dd className="mt-1 text-purple-text">{formatDate(selectedUser.sessions_revoked_at)}</dd></div>
                    </dl>
                  </section>

                  <section aria-labelledby="account-support-actions">
                    <h3 id="account-support-actions" className="text-sm font-semibold text-purple-text">Support actions</h3>
                    <p className="mt-1 text-xs leading-5 text-purple-muted">Each action requires your password, a reason, and creates an audit event.</p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <button type="button" disabled={selectedUser.role === 'admin' || selectedUser.email_verified || selectedUser.account_status !== 'active'} onClick={() => openAction(selectedUser, 'resend-verification')} className="flex min-h-12 items-center gap-3 rounded-xl border border-white/10 px-4 text-left text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-35"><MailIcon /><span>Resend verification</span></button>
                      <button type="button" disabled={selectedUser.role === 'admin' || selectedUser.account_status !== 'active'} onClick={() => openAction(selectedUser, 'send-password-reset')} className="flex min-h-12 items-center gap-3 rounded-xl border border-white/10 px-4 text-left text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-35"><KeyIcon /><span>Send password reset</span></button>
                      <button type="button" disabled={selectedUser.role === 'admin'} onClick={() => openAction(selectedUser, 'revoke-sessions')} className="flex min-h-12 items-center gap-3 rounded-xl border border-white/10 px-4 text-left text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-35"><SignOutIcon /><span>Force sign-out</span></button>
                      <button type="button" disabled={selectedUser.role === 'admin'} onClick={() => openAction(selectedUser, selectedUser.account_status === 'suspended' ? 'reactivate' : 'suspend')} className={`min-h-12 rounded-xl border px-4 text-left text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-35 ${selectedUser.account_status === 'suspended' ? 'border-emerald-400/20 text-emerald-300 hover:bg-emerald-500/10' : 'border-red-400/20 text-red-300 hover:bg-red-500/10'}`}>{selectedUser.account_status === 'suspended' ? 'Reactivate account' : 'Suspend account'}</button>
                    </div>
                  </section>

                  <section aria-labelledby="security-history-title">
                    <div className="flex items-end justify-between gap-3">
                      <div>
                        <h3 id="security-history-title" className="text-sm font-semibold text-purple-text">Security history</h3>
                        <p className="mt-1 text-xs text-purple-muted">Authentication, email, and administrative events.</p>
                      </div>
                      <span className="text-xs text-purple-muted">Latest {securityEvents.length}</span>
                    </div>
                    {securityEvents.length === 0 ? (
                      <div className={`${inset} mt-3`}><EmptyState>No security activity has been recorded yet.</EmptyState></div>
                    ) : (
                      <div className={`${inset} mt-3 divide-y divide-white/8 overflow-hidden`}>
                        {securityEvents.map((event) => (
                          <article key={`${event.category}-${event.id}`} className="p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-purple-text">{SECURITY_EVENT_LABELS[event.event_type] || event.event_type.replaceAll('_', ' ')}</p>
                                <p className="mt-1 text-xs capitalize text-purple-muted">{event.source.replaceAll('_', ' ')}{event.actor_username ? ` by ${event.actor_username}` : ''}</p>
                              </div>
                              <span className={`shrink-0 text-xs font-medium ${['success', 'sent'].includes(event.outcome) ? 'text-emerald-300' : event.outcome === 'queued' ? 'text-amber-300' : 'text-red-300'}`}>{event.outcome}</span>
                            </div>
                            {event.detail && <p className="mt-2 text-xs leading-5 text-purple-soft">{event.detail.replaceAll('_', ' ')}</p>}
                            <p className="mt-2 text-xs text-purple-muted">{formatDate(event.created_at)}</p>
                          </article>
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              )}
            </div>
          </aside>
        </div>
      )}

      {activityOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-end bg-black/65 backdrop-blur-sm sm:items-stretch" onMouseDown={(event) => event.target === event.currentTarget && closeActivity()}>
          <aside ref={activityPanelRef} role="dialog" aria-modal="true" aria-labelledby="admin-activity-title" className="flex max-h-[90vh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-[#180731] shadow-2xl sm:max-h-none sm:max-w-md sm:rounded-none sm:rounded-l-3xl">
            <div className="mx-auto mt-3 h-1 w-10 rounded-full bg-white/20 sm:hidden" />
            <div className="flex items-center justify-between gap-4 border-b border-white/8 p-5 sm:p-6">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-primary/15 text-purple-primary-light"><BellIcon /></span>
                <div className="min-w-0">
                  <h2 id="admin-activity-title" className="text-lg font-semibold text-purple-text">Audit history</h2>
                  <p className="mt-0.5 truncate text-sm text-purple-muted">Search and filter administrative actions</p>
                </div>
              </div>
              <button type="button" onClick={closeActivity} aria-label="Close notifications" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 text-purple-soft transition hover:bg-white/5 hover:text-purple-text">
                <CloseIcon />
              </button>
            </div>
            <form className="space-y-3 border-b border-white/8 p-4 sm:p-5" onSubmit={(event) => { event.preventDefault(); setAuditQuery(auditSearchDraft.trim()); setAuditPage(1); }}>
              <div className="flex gap-2">
                <label className="relative min-w-0 flex-1">
                  <span className="sr-only">Search administrator or target</span>
                  <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-purple-muted"><SearchIcon /></span>
                  <input className={`${control} pl-11`} value={auditSearchDraft} onChange={(event) => setAuditSearchDraft(event.target.value)} placeholder="Search actor or account" maxLength={100} />
                </label>
                <button type="submit" className="min-h-11 rounded-xl bg-purple-primary px-4 text-sm font-semibold text-white transition hover:bg-purple-primary-light">Search</button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <select className={control} value={auditAction} onChange={(event) => { setAuditAction(event.target.value); setAuditPage(1); }} aria-label="Filter audit action">
                  <option value="">All actions</option>
                  <option value="suspend_user">Suspensions</option>
                  <option value="reactivate_user">Reactivations</option>
                  <option value="resend_verification">Verification emails</option>
                  <option value="send_password_reset">Password resets</option>
                  <option value="revoke_sessions">Session revocations</option>
                  <option value="grant_admin">Admin grants</option>
                  <option value="revoke_admin">Admin revocations</option>
                </select>
                <select className={control} value={auditOutcome} onChange={(event) => { setAuditOutcome(event.target.value); setAuditPage(1); }} aria-label="Filter audit outcome">
                  <option value="">All outcomes</option>
                  <option value="success">Completed</option>
                  <option value="denied">Denied</option>
                </select>
                <select className={control} value={auditSource} onChange={(event) => { setAuditSource(event.target.value); setAuditPage(1); }} aria-label="Filter audit source">
                  <option value="">All sources</option>
                  <option value="web">Dashboard</option>
                  <option value="operator_cli">Terminal</option>
                </select>
                <button type="button" onClick={() => { setAuditSearchDraft(''); setAuditQuery(''); setAuditAction(''); setAuditOutcome(''); setAuditSource(''); setAuditDateFrom(''); setAuditDateTo(''); setAuditPage(1); }} className="min-h-11 rounded-xl border border-white/10 px-3 text-sm font-medium text-purple-soft transition hover:bg-white/5">Reset filters</button>
                <label className="text-xs text-purple-muted">From<input type="date" className={`${control} mt-1`} value={auditDateFrom} onChange={(event) => { setAuditDateFrom(event.target.value); setAuditPage(1); }} /></label>
                <label className="text-xs text-purple-muted">To<input type="date" className={`${control} mt-1`} value={auditDateTo} onChange={(event) => { setAuditDateTo(event.target.value); setAuditPage(1); }} /></label>
              </div>
            </form>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {auditLoading ? (
                <EmptyState>Loading audit activity…</EmptyState>
              ) : auditEvents.length === 0 ? (
                <EmptyState>No administrative actions have been recorded yet.</EmptyState>
              ) : (
                <div className="divide-y divide-white/6">
                  {auditEvents.map((event) => (
                    <article key={event.id} className="grid gap-2 px-5 py-4 sm:px-6">
                      <div className="min-w-0">
                        <p className="text-sm leading-6 text-purple-text">
                          <span className="font-semibold">{event.actor_username || 'Operator'}</span>{' '}
                          {AUDIT_ACTION_LABELS[event.action]?.toLowerCase() || event.action.replaceAll('_', ' ')}{' '}
                          <span className="font-semibold">{event.target_username || 'a removed account'}</span>
                        </p>
                        {event.reason && <p className="mt-1 text-xs leading-5 text-purple-muted">{event.reason}</p>}
                      </div>
                      <div className="flex items-center justify-between gap-3 text-xs text-purple-muted">
                        <span className={event.outcome === 'success' ? 'text-emerald-300' : 'text-red-300'}>{event.outcome === 'success' ? 'Completed' : 'Denied'}</span>
                        <span>{formatDate(event.created_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-white/8 p-4 sm:px-5">
              <p className="text-xs text-purple-muted">Page {auditPagination.page} of {auditPagination.pages}</p>
              <div className="flex gap-2">
                <button type="button" disabled={auditPage <= 1 || auditLoading} onClick={() => setAuditPage((current) => Math.max(1, current - 1))} className="min-h-10 rounded-xl border border-white/10 px-3 text-xs font-semibold text-purple-text disabled:opacity-35">Previous</button>
                <button type="button" disabled={auditPage >= auditPagination.pages || auditLoading} onClick={() => setAuditPage((current) => Math.min(auditPagination.pages, current + 1))} className="min-h-10 rounded-xl border border-white/10 px-3 text-xs font-semibold text-purple-text disabled:opacity-35">Next</button>
              </div>
            </div>
          </aside>
        </div>
      )}

      {action && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4" onMouseDown={(event) => event.target === event.currentTarget && closeAction()}>
          <div ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="admin-action-title" aria-describedby="admin-action-description" className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl border border-white/10 bg-purple-deep p-5 shadow-2xl sm:max-w-lg sm:rounded-2xl sm:p-6">
            <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-white/20 sm:hidden" />
            <h2 id="admin-action-title" className={`text-xl font-semibold ${actionTitleClass}`}>{actionText}</h2>
            <p id="admin-action-description" className="mt-2 text-sm leading-6 text-purple-soft">
              {actionConfig?.description} Target account: <span className="font-semibold text-purple-text">{action.user.username}</span>.
            </p>
            {actionError && <div role="alert" className="mt-4 rounded-xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-200">{actionError}</div>}
            <div className="mt-5 space-y-4">
              <div>
                <label htmlFor="admin-password" className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-purple-muted">Your current password</label>
                <input ref={passwordRef} id="admin-password" type="password" className={control} value={password} onChange={(event) => setPassword(event.target.value)} disabled={submitting} autoComplete="current-password" />
              </div>
              <div>
                <label htmlFor="admin-reason" className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-purple-muted">Reason</label>
                <textarea id="admin-reason" className={`${control} min-h-24 resize-y`} value={reason} onChange={(event) => setReason(event.target.value)} disabled={submitting} minLength={5} maxLength={250} placeholder="Brief reason for this account-access change" />
                <p className="mt-1.5 text-right text-xs text-purple-muted">{reason.trim().length}/250</p>
              </div>
            </div>
            <div className="mt-6 grid grid-cols-2 gap-3">
              <button type="button" onClick={closeAction} disabled={submitting} className="min-h-12 rounded-xl border border-white/10 text-sm font-semibold text-purple-text transition hover:bg-white/5 disabled:opacity-50">Cancel</button>
              <button type="button" onClick={submitAction} disabled={submitting || !password || reason.trim().length < 5} className={`min-h-12 rounded-xl text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-40 ${actionButtonClass}`}>{submitting ? 'Saving…' : actionText}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
