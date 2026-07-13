import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { apiFetch, parseApiResponse, primeCsrf, checkAuth } from '../api';
import { useCategories } from '../components/CategoriesContext';
import CategoryBadge, { CategoryIconBox } from '../components/CategoryBadge';
import {
  categorizeItem,
  categoryLabel,
  CUSTOM_CATEGORY_COLORS,
} from '../utils/categorize';
import {
  card, cardInner, input, label, btnPrimary, subtext,
} from '../utils/theme';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function Alert({ type, children }) {
  const tones = {
    error: 'border-red-400/20 bg-red-500/10 text-red-300',
    success: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
  };
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${tones[type]}`}>
      {children}
    </div>
  );
}

function SectionTitle({ children, right }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2.5">
        <span className="h-4 w-1 rounded-full bg-gradient-to-b from-purple-primary to-purple-primary-light" />
        <h2 className="text-base font-semibold tracking-tight text-purple-text">{children}</h2>
      </div>
      {right}
    </div>
  );
}

function MiniRing({ value, max, size = 56, stroke = 5 }) {
  const pct = max ? Math.min((value / max) * 100, 100) : 0;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} stroke="rgba(139,60,224,0.15)" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#b982ff" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-sm font-bold leading-none text-purple-text">{value}</span>
        <span className="text-[8px] font-medium uppercase tracking-wider text-purple-muted">/{max}</span>
      </div>
    </div>
  );
}

function BudgetSnapshot({
  limitsSet, limitsCategories, weeklyTotal, monthlyTotal, activeCount, totalCount, topRecurring, categoryCount,
}) {
  const hasRecurring = activeCount > 0;
  const limitsLabel = limitsSet === 0
    ? 'No caps yet'
    : limitsSet === 1
      ? '1 category capped'
      : `${limitsSet} categories capped`;

  return (
    <div className={`${card} budget-snapshot p-0`}>
      <div className="budget-snapshot-grid">
        <div className="budget-snapshot-zone budget-snapshot-zone--limits">
          <div className="flex items-center gap-4">
            <MiniRing value={limitsSet} max={categoryCount} />
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-purple-muted">Category caps</p>
              <p className="mt-0.5 text-base font-semibold text-purple-text">{limitsLabel}</p>
              {limitsSet > 0 && limitsCategories.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {limitsCategories.map((c) => (
                    <CategoryIconBox key={c} category={c} className="!h-6 !w-6 !rounded-lg [&_svg]:!h-3 [&_svg]:!w-3" />
                  ))}
                </div>
              )}
              {limitsSet === 0 && (
                <p className="mt-1 text-xs text-purple-muted">Set weekly limits below</p>
              )}
            </div>
          </div>
        </div>

        <div className="budget-snapshot-divider" aria-hidden="true" />

        <div className="budget-snapshot-zone budget-snapshot-zone--recurring">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-purple-muted">Fixed bills</p>
          {hasRecurring ? (
            <>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0">
                {monthlyTotal > 0 && (
                  <span className="text-2xl font-bold tracking-tight text-purple-text">
                    ₱{monthlyTotal.toLocaleString()}
                    <span className="ml-1 text-sm font-medium text-purple-muted">/mo</span>
                  </span>
                )}
                {weeklyTotal > 0 && (
                  <span className={`font-semibold text-purple-primary-light ${monthlyTotal > 0 ? 'text-base' : 'text-2xl'}`}>
                    ₱{weeklyTotal.toLocaleString()}
                    <span className="ml-0.5 text-sm font-medium text-purple-muted">/wk</span>
                  </span>
                )}
                {monthlyTotal === 0 && weeklyTotal === 0 && (
                  <span className="text-2xl font-bold text-purple-text">₱0</span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-purple-primary/15 px-2.5 py-0.5 text-[11px] font-medium text-purple-primary-light">
                  {activeCount} active
                </span>
                {totalCount > activeCount && (
                  <span className="text-[11px] text-purple-muted">{totalCount - activeCount} paused</span>
                )}
                {topRecurring && (
                  <span className="text-[11px] text-purple-muted">
                    {topRecurring.name}
                  </span>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="mt-0.5 text-base font-semibold text-purple-text">Nothing scheduled</p>
              <p className="mt-1 text-xs text-purple-muted">Add rent, subs, or other fixed bills</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RecurringCard({ item, onToggle, onDelete }) {
  return (
    <li className={`${cardInner} flex items-start justify-between gap-3 p-3.5 transition ${item.active ? '' : 'opacity-60'}`}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className={`text-sm font-medium ${item.active ? 'text-purple-text' : 'text-purple-muted line-through'}`}>
            {item.name}
          </p>
          <CategoryBadge category={item.category} />
        </div>
        <p className="mt-1.5 text-lg font-semibold text-purple-primary-light">
          ₱{item.amount.toFixed(2)}
        </p>
        <p className="mt-0.5 text-xs text-purple-muted">
          {item.frequency === 'weekly' && item.apply_day
            ? `Every ${item.apply_day}`
            : `Day ${item.apply_day_of_month} of each month`}
          {!item.active && ' (paused)'}
        </p>
      </div>
      <div className="flex shrink-0 flex-col gap-1.5 sm:flex-row">
        <button
          type="button"
          className="glass-btn-ghost rounded-lg px-2.5 py-1.5 text-xs font-medium text-purple-soft hover:text-purple-text"
          onClick={() => onToggle(item)}
        >
          {item.active ? 'Pause' : 'Resume'}
        </button>
        <button
          type="button"
          className="rounded-lg border border-red-400/20 bg-red-500/10 px-2.5 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-500/20"
          onClick={() => onDelete(item.id)}
        >
          Remove
        </button>
      </div>
    </li>
  );
}

export default function BudgetSetup() {
  const navigate = useNavigate();
  const {
    categories,
    labels,
    customCategories,
    setCustomCategories,
  } = useCategories();
  const [loading, setLoading] = useState(true);
  const [categoryLimits, setCategoryLimits] = useState({});
  const [limitsSaving, setLimitsSaving] = useState(false);
  const [limitsMessage, setLimitsMessage] = useState('');
  const [limitsError, setLimitsError] = useState('');

  const [recurring, setRecurring] = useState([]);
  const [recName, setRecName] = useState('');
  const [recAmount, setRecAmount] = useState('');
  const [recCategory, setRecCategory] = useState('other');
  const [recFrequency, setRecFrequency] = useState('weekly');
  const [recApplyDay, setRecApplyDay] = useState('Sunday');
  const [recDayOfMonth, setRecDayOfMonth] = useState('1');
  const [recSaving, setRecSaving] = useState(false);
  const [recError, setRecError] = useState('');
  const [recMessage, setRecMessage] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  const [customLabel, setCustomLabel] = useState('');
  const [customColor, setCustomColor] = useState(CUSTOM_CATEGORY_COLORS[0]);
  const [customSaving, setCustomSaving] = useState(false);
  const [customError, setCustomError] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [customModalOpen, setCustomModalOpen] = useState(false);

  useEffect(() => {
    primeCsrf();

    checkAuth()
      .then((d) => {
        if (!d.authenticated) {
          navigate('/');
          return;
        }
        return apiFetch('/api/budget-settings');
      })
      .then((r) => {
        if (!r) return;
        if (r.status === 401) {
          navigate('/');
          return;
        }
        return r.json();
      })
      .then((d) => {
        if (!d) return;
        if (d.category_limits) setCategoryLimits(d.category_limits);
        if (d.recurring_expenses) setRecurring(d.recurring_expenses);
        if (d.custom_categories) setCustomCategories(d.custom_categories);
      })
      .catch(() => navigate('/'))
      .finally(() => setLoading(false));
  }, [navigate, setCustomCategories]);

  useEffect(() => {
    if (recName.trim()) setRecCategory(categorizeItem(recName, null, categories));
  }, [recName, categories]);

  const limitsCategories = useMemo(
    () => categories.filter((c) => {
      const v = categoryLimits[c];
      return v !== '' && v != null && Number(v) > 0;
    }),
    [categoryLimits, categories],
  );

  const limitsSet = limitsCategories.length;

  const activeRecurring = useMemo(
    () => recurring.filter((r) => r.active),
    [recurring],
  );

  const topRecurring = useMemo(
    () => (activeRecurring.length > 0
      ? [...activeRecurring].sort((a, b) => b.amount - a.amount)[0]
      : null),
    [activeRecurring],
  );

  const weeklyRecurringTotal = useMemo(
    () => activeRecurring
      .filter((r) => r.frequency === 'weekly')
      .reduce((s, r) => s + r.amount, 0),
    [activeRecurring],
  );

  const monthlyRecurringTotal = useMemo(
    () => activeRecurring
      .filter((r) => r.frequency === 'monthly')
      .reduce((s, r) => s + r.amount, 0),
    [activeRecurring],
  );

  const saveCategoryLimits = async () => {
    setLimitsError('');
    setLimitsMessage('');
    setLimitsSaving(true);
    try {
      const limits = {};
      for (const c of categories) {
        const raw = categoryLimits[c];
        limits[c] = raw === '' || raw == null ? null : parseFloat(raw);
      }
      const res = await apiFetch('/api/category-limits', {
        method: 'PUT',
        body: JSON.stringify({ limits }),
      });
      const { data, ok } = await parseApiResponse(res);
      if (ok) {
        setLimitsMessage('Category limits saved.');
        if (data.category_limits) setCategoryLimits(data.category_limits);
      } else {
        setLimitsError(data.error || 'Could not save limits.');
      }
    } catch {
      setLimitsError('Could not reach the server.');
    } finally {
      setLimitsSaving(false);
    }
  };

  const openCustomModal = () => {
    setCustomError('');
    setCustomMessage('');
    setCustomModalOpen(true);
  };

  const closeCustomModal = () => {
    setCustomModalOpen(false);
    setCustomError('');
    setCustomMessage('');
    setCustomLabel('');
  };

  const addCustomCategory = async () => {
    setCustomError('');
    setCustomMessage('');
    const name = customLabel.trim();
    if (!name) {
      setCustomError('Enter a category name.');
      return;
    }
    setCustomSaving(true);
    try {
      const res = await apiFetch('/api/user-categories', {
        method: 'POST',
        body: JSON.stringify({ label: name, color: customColor }),
      });
      const { data, ok } = await parseApiResponse(res);
      if (!ok) {
        setCustomError(data.error || 'Could not create category.');
        return;
      }
      setCustomCategories(data.custom_categories || []);
      setCustomLabel('');
      setCustomColor(CUSTOM_CATEGORY_COLORS[(customCategories.length + 1) % CUSTOM_CATEGORY_COLORS.length]);
      setCustomMessage(`Added “${data.category?.label || name}”.`);
    } catch {
      setCustomError('Could not create category.');
    } finally {
      setCustomSaving(false);
    }
  };

  const deleteCustomCategory = async (categoryId, categoryName) => {
    if (!window.confirm(`Delete “${categoryName}”? Existing items move to Other.`)) return;
    setCustomError('');
    setCustomMessage('');
    try {
      const res = await apiFetch(`/api/user-categories/${categoryId}`, { method: 'DELETE' });
      const { data, ok } = await parseApiResponse(res);
      if (!ok) {
        setCustomError(data.error || 'Could not delete category.');
        return;
      }
      setCustomCategories(data.custom_categories || []);
      setCategoryLimits((prev) => {
        const next = { ...prev };
        const removed = customCategories.find((c) => c.id === categoryId);
        if (removed) delete next[removed.slug];
        return next;
      });
      setCustomMessage('Category deleted.');
    } catch {
      setCustomError('Could not delete category.');
    }
  };

  const addRecurring = async () => {
    setRecError('');
    setRecMessage('');
    const name = recName.trim();
    const amount = parseFloat(recAmount);
    if (!name) {
      setRecError('Enter a name for the recurring expense.');
      return;
    }
    if (!amount || amount <= 0) {
      setRecError('Enter a valid amount.');
      return;
    }
    setRecSaving(true);
    try {
      const body = {
        name,
        amount,
        category: recCategory,
        frequency: recFrequency,
      };
      if (recFrequency === 'weekly') {
        body.apply_day = recApplyDay;
      } else {
        body.apply_day_of_month = parseInt(recDayOfMonth, 10) || 1;
      }
      const res = await apiFetch('/api/recurring-expenses', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const { data, ok } = await parseApiResponse(res);
      if (ok) {
        setRecMessage('Recurring expense added.');
        setRecurring(data.recurring_expenses || []);
        setRecName('');
        setRecAmount('');
        setRecCategory('other');
        setShowAddForm(false);
      } else {
        setRecError(data.error || 'Could not add recurring expense.');
      }
    } catch {
      setRecError('Could not reach the server.');
    } finally {
      setRecSaving(false);
    }
  };

  const toggleRecurring = async (item) => {
    try {
      const res = await apiFetch(`/api/recurring-expenses/${item.id}`, {
        method: 'PUT',
        body: JSON.stringify({ active: !item.active }),
      });
      const { data, ok } = await parseApiResponse(res);
      if (ok) setRecurring(data.recurring_expenses || []);
    } catch {}
  };

  const deleteRecurring = async (id) => {
    if (!confirm('Remove this recurring expense?')) return;
    try {
      const res = await apiFetch(`/api/recurring-expenses/${id}`, { method: 'DELETE' });
      const { data, ok } = await parseApiResponse(res);
      if (ok) setRecurring(data.recurring_expenses || []);
    } catch {}
  };

  useEffect(() => {
    if (!customModalOpen) return undefined;
    const onKey = (e) => e.key === 'Escape' && closeCustomModal();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [customModalOpen]);

  if (loading) {
    return (
      <div className="flex min-h-[280px] items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-purple-primary/30 border-t-purple-primary login-spinner" />
      </div>
    );
  }

  return (
    <div className="w-full space-y-5">
      <BudgetSnapshot
        limitsSet={limitsSet}
        limitsCategories={limitsCategories}
        categoryCount={categories.length}
        weeklyTotal={weeklyRecurringTotal}
        monthlyTotal={monthlyRecurringTotal}
        activeCount={activeRecurring.length}
        totalCount={recurring.length}
        topRecurring={topRecurring}
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className={`${card} p-5`}>
          <SectionTitle
            right={(
              <button
                type="button"
                onClick={openCustomModal}
                className="glass-btn-ghost rounded-lg px-3 py-1.5 text-xs font-medium text-purple-soft hover:text-purple-text"
              >
                + Custom
              </button>
            )}
          >
            Category limits
          </SectionTitle>
          <p className={`mb-4 ${subtext}`}>
            Optional weekly caps per category. Leave blank for no limit. Warnings show on the dashboard when you get close or go over.
          </p>

          {limitsError && <div className="mb-4"><Alert type="error">{limitsError}</Alert></div>}
          {limitsMessage && <div className="mb-4"><Alert type="success">{limitsMessage}</Alert></div>}

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {categories.map((c) => {
              const hasLimit = categoryLimits[c] !== '' && categoryLimits[c] != null && Number(categoryLimits[c]) > 0;
              return (
                <div
                  key={c}
                  className={`${cardInner} flex items-center gap-3 p-3 transition ${hasLimit ? 'border-purple-primary/25 ring-1 ring-purple-primary/10' : ''}`}
                >
                  <CategoryIconBox category={c} />
                  <div className="min-w-0 flex-1">
                    <label className="block truncate text-xs font-medium text-purple-text-dim">
                      {categoryLabel(c, labels)}
                    </label>
                    <div className="relative mt-1">
                      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-purple-muted">₱</span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        className={`${input} py-2 pl-7 pr-3 text-sm`}
                        placeholder="No limit"
                        value={categoryLimits[c] ?? ''}
                        onChange={(e) => setCategoryLimits((prev) => ({ ...prev, [c]: e.target.value }))}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <button
            type="button"
            disabled={limitsSaving}
            onClick={saveCategoryLimits}
            className={`${btnPrimary} mt-5 w-full`}
          >
            {limitsSaving ? 'Saving…' : 'Save category limits'}
          </button>
        </section>

        <section className={`${card} p-5`}>
          <SectionTitle
            right={(
              <button
                type="button"
                onClick={() => setShowAddForm((v) => !v)}
                className="glass-btn-ghost rounded-lg px-3 py-1.5 text-xs font-medium text-purple-soft hover:text-purple-text"
              >
                {showAddForm ? 'Cancel' : '+ Add new'}
              </button>
            )}
          >
            Recurring expenses
          </SectionTitle>
          <p className={`mb-4 ${subtext}`}>
            Bills on a schedule: rent, subscriptions, load, and the like. The app logs them for you so you don&apos;t re-type every week.
          </p>

          <button
            type="button"
            onClick={() => setHelpOpen((v) => !v)}
            className={`${cardInner} mb-4 flex w-full items-center justify-between px-4 py-3 text-left text-sm transition hover:border-purple-primary/20`}
          >
            <span className="font-medium text-purple-text">How auto-logging works</span>
            <svg
              viewBox="0 0 24 24"
              className={`h-4 w-4 text-purple-muted transition-transform ${helpOpen ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>

          {helpOpen && (
            <div className={`${cardInner} mb-4 px-4 py-3 text-xs leading-relaxed text-purple-muted`}>
              <ol className="list-decimal space-y-1.5 pl-4">
                <li>Set your <strong className="text-purple-soft">weekly allowance</strong> on the dashboard first.</li>
                <li><strong className="text-purple-soft">Weekly</strong> items post once per week on the day you pick.</li>
                <li><strong className="text-purple-soft">Monthly</strong> items post on your billing date (e.g. rent on the 1st).</li>
                <li>Charges show up under that day in Log expense, same as a manual entry.</li>
              </ol>
            </div>
          )}

          {recError && <div className="mb-4"><Alert type="error">{recError}</Alert></div>}
          {recMessage && <div className="mb-4"><Alert type="success">{recMessage}</Alert></div>}

          {recurring.length === 0 && !showAddForm && (
            <div className={`${cardInner} mb-4 py-10 text-center`}>
              <p className="text-sm font-medium text-purple-text">No recurring expenses yet</p>
              <p className={`mt-1 ${subtext}`}>Add rent, subscriptions, or other fixed bills.</p>
              <button
                type="button"
                onClick={() => setShowAddForm(true)}
                className={`${btnPrimary} mt-4 px-4 py-2 text-xs`}
              >
                Add your first recurring expense
              </button>
            </div>
          )}

          {recurring.length > 0 && (
            <ul className="mb-4 space-y-2">
              {recurring.map((item) => (
                <RecurringCard
                  key={item.id}
                  item={item}
                  onToggle={toggleRecurring}
                  onDelete={deleteRecurring}
                />
              ))}
            </ul>
          )}

          {showAddForm && (
            <div className={`${cardInner} space-y-4 p-4`}>
              <p className="text-xs font-medium uppercase tracking-wider text-purple-muted">New recurring expense</p>
              <div>
                <label className={label}>Name</label>
                <input
                  className={input}
                  value={recName}
                  onChange={(e) => setRecName(e.target.value)}
                  placeholder="Netflix, rent, Spotify…"
                  onKeyDown={(e) => e.key === 'Enter' && addRecurring()}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={label}>Amount</label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-purple-muted">₱</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className={`${input} pl-7`}
                      value={recAmount}
                      onChange={(e) => setRecAmount(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <label className={label}>Category</label>
                  <select className={input} value={recCategory} onChange={(e) => setRecCategory(e.target.value)}>
                    {categories.map((c) => (
                      <option key={c} value={c}>{categoryLabel(c, labels)}</option>
                    ))}
                  </select>
                </div>
              </div>

              {recName.trim() && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-purple-muted">Suggested</span>
                  <CategoryBadge category={recCategory} />
                </div>
              )}

              <div>
                <label className={label}>Frequency</label>
                <div className="grid grid-cols-2 gap-2">
                  {['weekly', 'monthly'].map((freq) => (
                    <button
                      key={freq}
                      type="button"
                      onClick={() => setRecFrequency(freq)}
                      className={`rounded-xl border px-3 py-2.5 text-sm font-medium capitalize transition ${
                        recFrequency === freq
                          ? 'border-purple-primary/40 bg-purple-primary/20 text-purple-text shadow-glow'
                          : 'glass-surface text-purple-soft hover:bg-purple-primary/10'
                      }`}
                    >
                      {freq}
                    </button>
                  ))}
                </div>
              </div>

              {recFrequency === 'weekly' ? (
                <div>
                  <label className={label}>Day of week</label>
                  <div className="grid grid-cols-7 gap-1">
                    {DAYS.map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setRecApplyDay(d)}
                        className={`rounded-full py-2 text-[10px] font-medium transition ${
                          recApplyDay === d
                            ? 'bg-purple-primary text-white shadow-glow'
                            : 'glass-surface text-purple-muted hover:text-purple-text'
                        }`}
                        title={d}
                      >
                        {d.slice(0, 3)}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div>
                  <label className={label}>Billing date (day of month)</label>
                  <input
                    type="number"
                    min="1"
                    max="31"
                    className={input}
                    value={recDayOfMonth}
                    onChange={(e) => setRecDayOfMonth(e.target.value)}
                    placeholder="1"
                  />
                  <p className="mt-1 text-[10px] text-purple-muted">
                    e.g. 1 for bills due on the 1st of each month.
                  </p>
                </div>
              )}

              <button
                type="button"
                disabled={recSaving}
                onClick={addRecurring}
                className={`${btnPrimary} w-full`}
              >
                {recSaving ? 'Adding…' : 'Add recurring expense'}
              </button>
            </div>
          )}
        </section>
      </div>

      {customModalOpen && createPortal(
        <div
          className="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
          onClick={closeCustomModal}
          style={{ animation: 'fadeIn 0.2s ease-out' }}
        >
          <div
            className={`${card} flex max-h-[92vh] w-full max-w-md flex-col overflow-hidden rounded-b-none rounded-t-3xl sm:rounded-3xl`}
            onClick={(e) => e.stopPropagation()}
            style={{ animation: 'fadeIn 0.28s cubic-bezier(0.16,1,0.3,1)' }}
          >
            <div className="flex items-start justify-between gap-4 border-b border-purple-primary/10 px-5 py-4">
              <div>
                <h3 className="text-base font-semibold tracking-tight text-purple-text">Custom categories</h3>
                <p className="mt-0.5 text-xs text-purple-muted">
                  Add your own beyond the built-in set.
                </p>
              </div>
              <button
                type="button"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-purple-muted transition hover:bg-purple-primary/10 hover:text-purple-text"
                onClick={closeCustomModal}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="no-scrollbar space-y-4 overflow-y-auto px-5 py-4">
              {customError && <Alert type="error">{customError}</Alert>}
              {customMessage && <Alert type="success">{customMessage}</Alert>}

              {customCategories.length > 0 && (
                <ul className="space-y-2">
                  {customCategories.map((cat) => (
                    <li key={cat.id} className={`${cardInner} flex items-center justify-between gap-3 p-3`}>
                      <div className="flex min-w-0 items-center gap-3">
                        <span
                          className="h-7 w-7 shrink-0 rounded-lg border"
                          style={{
                            backgroundColor: `${cat.color}26`,
                            borderColor: `${cat.color}47`,
                          }}
                          aria-hidden="true"
                        />
                        <p className="truncate text-sm font-medium text-purple-text">{cat.label}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => deleteCustomCategory(cat.id, cat.label)}
                        className="shrink-0 text-xs font-medium text-purple-muted transition hover:text-red-400"
                      >
                        Delete
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div className="space-y-3">
                <div>
                  <label className={label}>Name</label>
                  <input
                    className={input}
                    value={customLabel}
                    onChange={(e) => setCustomLabel(e.target.value)}
                    placeholder="Pets, Tuition, Gadgets…"
                    maxLength={40}
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && addCustomCategory()}
                  />
                </div>
                <div>
                  <label className={label}>Color</label>
                  <div className="flex flex-wrap gap-2">
                    {CUSTOM_CATEGORY_COLORS.map((color) => (
                      <button
                        key={color}
                        type="button"
                        onClick={() => setCustomColor(color)}
                        className={`h-8 w-8 rounded-full border-2 transition ${
                          customColor === color ? 'border-purple-text scale-110' : 'border-transparent'
                        }`}
                        style={{ backgroundColor: color }}
                        aria-label={`Pick color ${color}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-purple-primary/10 px-5 py-4">
              <button
                type="button"
                onClick={closeCustomModal}
                className="glass-btn-ghost rounded-lg px-3 py-2 text-xs font-medium text-purple-soft hover:text-purple-text"
              >
                Done
              </button>
              <button
                type="button"
                disabled={customSaving}
                onClick={addCustomCategory}
                className={`${btnPrimary} px-4 py-2 text-xs`}
              >
                {customSaving ? 'Adding…' : 'Add category'}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
