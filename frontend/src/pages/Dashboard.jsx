import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { apiFetch, openPdf } from '../api';
import {
  categorizeItem,
  CATEGORIES,
  CATEGORY_LABELS,
  CATEGORY_ICONS,
  CATEGORY_COLORS,
} from '../utils/categorize';
import {
  card, cardInner, input, label, btnPrimary,
  heading, subtext, statLabel,
} from '../utils/theme';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const ICON = 'h-[18px] w-[18px]';
const svgProps = {
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', className: ICON,
};

const SunIcon = () => (
  <svg {...svgProps}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
  </svg>
);
const MoonIcon = () => (
  <svg {...svgProps}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
);
const ExportIcon = () => (
  <svg {...svgProps}>
    <path d="M12 3v12" /><path d="m8 11 4 4 4-4" /><path d="M20 17v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2" />
  </svg>
);
const LogoutIcon = () => (
  <svg {...svgProps}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" />
  </svg>
);
const MenuIcon = () => (
  <svg {...svgProps}><path d="M3 6h18M3 12h18M3 18h18" /></svg>
);

function IconButton({ onClick, label, danger, className = '', children }) {
  const base =
    'items-center justify-center gap-2 rounded-xl border h-10 px-3 text-sm font-medium transition active:scale-[0.97]';
  const tone = danger
    ? 'border-red-400/25 bg-red-500/10 text-red-300 hover:bg-red-500/20 light:border-red-200 light:bg-white light:text-red-600 light:shadow-sm light:hover:bg-red-50'
    : 'border-purple-primary/15 bg-purple-deep/40 text-purple-text-dim hover:border-purple-primary/40 hover:bg-purple-primary/12 hover:text-purple-text light:border-purple-border light:bg-white light:text-purple-text light:shadow-sm light:hover:border-purple-primary/40 light:hover:bg-purple-primary/[0.06]';
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label} className={`${base} ${tone} ${className}`}>
      {children}
    </button>
  );
}

function MobileMenu({ open, onClose, darkMode, onTheme, showExport, onExport, onLogout, currentMonth, currentYear }) {
  const itemCls = 'mb-2 block w-full rounded-xl px-4 py-3 text-left text-sm font-medium text-purple-text-dim transition hover:bg-purple-primary/10 hover:text-purple-text';
  return (
    <>
      <div className={`fixed inset-0 z-[1999] bg-black/60 backdrop-blur-sm ${open ? 'block' : 'hidden'}`} onClick={onClose} />
      <div className={`fixed right-0 top-0 z-[2000] h-screen w-72 border-l border-purple-primary/10 bg-purple-deep/95 p-6 backdrop-blur-xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="mb-8 flex items-center justify-between">
          <span className="font-semibold text-purple-text">Menu</span>
          <button type="button" className="text-purple-muted transition hover:text-purple-text" onClick={onClose}>✕</button>
        </div>
        <button type="button" className={itemCls} onClick={() => { onTheme(); onClose(); }}>
          {darkMode ? 'Light mode' : 'Dark mode'}
        </button>
        {showExport && (
          <button type="button" className={itemCls} onClick={() => { onExport(); onClose(); }}>Export PDF</button>
        )}
        <button type="button" className={itemCls} onClick={() => { openPdf(`/api/export-monthly-pdf?month=${currentMonth}&year=${currentYear}`); onClose(); }}>
          Monthly PDF
        </button>
        <button type="button" className={`${itemCls} text-red-300 hover:bg-red-500/10`} onClick={() => { onLogout(); onClose(); }}>
          Logout
        </button>
      </div>
    </>
  );
}

function SetupScreen({ weekInfo, onStart }) {
  const [val, setVal] = useState('');
  const [loading, setLoading] = useState(false);

  const start = async () => {
    const n = parseFloat(val);
    if (!n || n <= 0) return alert('Enter valid allowance');
    setLoading(true);
    try {
      const r = await apiFetch('/api/set-allowance', {
        method: 'POST',
        body: JSON.stringify({ allowance: n }),
      });
      if (r.ok) onStart(n);
    } catch {
      alert('Server error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-center py-16">
      <div className={`${card} w-full max-w-md p-8 text-center`}>
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-primary to-purple-primary-light shadow-glow ring-1 ring-inset ring-white/15">
          <span className="text-lg font-semibold text-white">₱</span>
        </div>
        <h2 className="mb-1 text-xl font-semibold text-purple-text">Start your week</h2>
        {weekInfo && (
          <p className={`mb-1 ${subtext}`}>
            {weekInfo.week_start_formatted} – {weekInfo.week_end_formatted}
          </p>
        )}
        <p className="mb-6 text-xs text-purple-muted">Week starts Sunday</p>
        <div className="text-left">
          <label htmlFor="allowanceInput" className={label}>Weekly allowance</label>
          <input
            type="number"
            id="allowanceInput"
            className={input}
            placeholder="1000"
            min="0"
            step="0.01"
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && start()}
          />
          <button type="button" className={`${btnPrimary} mt-4 w-full`} onClick={start} disabled={loading}>
            {loading ? 'Starting…' : 'Begin tracking'}
          </button>
        </div>
      </div>
    </div>
  );
}

function CategoryBadge({ category }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CATEGORY_COLORS[category]}`}>
      <span className="opacity-60">{CATEGORY_ICONS[category]}</span>
      {CATEGORY_LABELS[category]}
    </span>
  );
}

function RingProgress({ value, size = 128, stroke = 11, caption = 'used', centerLabel }) {
  const pct = Number.isFinite(value) ? value : 0;
  const arc = Math.max(0, Math.min(pct, 100));
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (arc / 100) * circ;
  const over = pct > 100;
  const color = over ? '#f87171' : pct > 80 ? '#fbbf24' : '#9d4edd';
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} stroke="rgba(157,78,221,0.16)" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.9s cubic-bezier(0.16,1,0.3,1)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-2xl font-semibold tracking-tight ${over ? 'text-red-400' : 'text-purple-text'}`}>
          {centerLabel ?? `${Math.round(pct)}%`}
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-purple-muted">{caption}</span>
      </div>
    </div>
  );
}

function MiniBars({ data, height = 96 }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="flex items-end gap-1.5" style={{ height }}>
      {data.map((d, i) => {
        const h = (d.value / max) * 100;
        return (
          <div key={i} className="group flex h-full flex-1 flex-col items-center gap-1.5">
            <div className="flex w-full flex-1 items-end justify-center">
              <div
                className={`w-full max-w-[26px] rounded-t-md transition-all duration-700 ${d.value > 0 ? 'bg-gradient-to-t from-purple-primary to-purple-primary-light group-hover:from-purple-primary-light group-hover:to-purple-primary' : 'bg-purple-deep/70'}`}
                style={{ height: `${Math.max(h, d.value > 0 ? 6 : 3)}%` }}
                title={`${d.label}: ₱${d.value.toFixed(2)}`}
              />
            </div>
            <span className="text-[10px] font-medium text-purple-muted">{d.short}</span>
          </div>
        );
      })}
    </div>
  );
}

function SectionTitle({ children, right, className = '' }) {
  return (
    <div className={`flex items-center justify-between gap-3 ${className}`}>
      <div className="flex items-center gap-2.5">
        <span className="h-4 w-1 rounded-full bg-gradient-to-b from-purple-primary to-purple-primary-light" />
        <h3 className={heading}>{children}</h3>
      </div>
      {right}
    </div>
  );
}

function WeeklyTracker({ weekInfo, allowance, expenses, totals, onRefresh }) {
  const today = new Date().getDay();
  const [selDay, setSelDay] = useState(DAYS[today]);
  const [itemName, setItemName] = useState('');
  const [itemAmount, setItemAmount] = useState('');
  const [category, setCategory] = useState('other');
  const [adding, setAdding] = useState(false);
  const [modalDay, setModalDay] = useState(null);

  useEffect(() => {
    if (itemName.trim()) setCategory(categorizeItem(itemName));
  }, [itemName]);

  const selectDay = (day, i) => {
    if (i > today) return;
    setSelDay(day);
    setItemName('');
    setItemAmount('');
    setCategory('other');
  };

  const dayItems = selDay && expenses[selDay]?.items ? expenses[selDay].items : [];
  const dayTotals = selDay && expenses[selDay] ? expenses[selDay] : { fare: 0, food: 0, other: 0, total: 0 };

  const addItem = async () => {
    if (!selDay) return;
    const name = itemName.trim();
    const amount = parseFloat(itemAmount);
    if (!name) return alert('Enter an item name');
    if (!amount || amount <= 0) return alert('Enter a valid amount');
    setAdding(true);
    try {
      const r = await apiFetch('/api/add-expense-item', {
        method: 'POST',
        body: JSON.stringify({ day: selDay, name, amount, category }),
      });
      if (r.ok) {
        setItemName('');
        setItemAmount('');
        setCategory('other');
        onRefresh();
      } else {
        const d = await r.json();
        alert(d.error || 'Failed to add item');
      }
    } catch {
      alert('Server error');
    } finally {
      setAdding(false);
    }
  };

  const deleteItem = async (itemId) => {
    if (!confirm('Remove this item?')) return;
    try {
      await apiFetch(`/api/delete-expense-item/${itemId}`, { method: 'DELETE' });
      onRefresh();
    } catch {
      alert('Server error');
    }
  };

  const deleteDay = async (day) => {
    if (!confirm(`Delete all expenses for ${day}?`)) return;
    try {
      await apiFetch(`/api/delete-expense/${day}`, { method: 'DELETE' });
      onRefresh();
    } catch {
      alert('Server error');
    }
  };

  const pct = allowance ? (totals.spent / allowance) * 100 : 0;
  const barColor = pct > 100 ? 'bg-red-400' : pct > 80 ? 'bg-amber-400' : 'bg-purple-primary';

  const expenseRows = DAYS.map((day, i) => {
    const e = expenses[day];
    const isToday = i === today;
    if (i > today || (isToday && !e)) return null;
    return { day, i, e, isToday };
  }).filter(Boolean);

  return (
    <div className="space-y-5">
      {weekInfo && (
        <div className={`${card} flex flex-col divide-y divide-purple-primary/10 sm:flex-row sm:items-center sm:divide-x sm:divide-y-0`}>
          <div className="flex-1 px-6 py-4 text-center">
            <p className={statLabel}>Current week</p>
            <p className="mt-0.5 text-sm font-medium text-purple-text">
              {weekInfo.week_start_formatted} – {weekInfo.week_end_formatted}
            </p>
          </div>
          <div className="flex-1 px-6 py-4 text-center">
            <p className={statLabel}>Days left</p>
            <p className="text-2xl font-semibold text-purple-primary-light sm:text-3xl">{weekInfo.days_remaining}</p>
          </div>
          <div className="flex-1 px-6 py-4 text-center">
            <p className={statLabel}>Today</p>
            <p className="mt-0.5 text-sm font-medium text-purple-text">{weekInfo.current_day}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[260px_1fr]">
        <div className={`${card} p-5`}>
          <SectionTitle className="mb-4">Overview</SectionTitle>
          <div className="mb-5 flex flex-col items-center rounded-2xl bg-purple-deep/40 py-5">
            <RingProgress value={pct} />
            <p className="mt-3 text-center text-xs text-purple-muted">
              <span className="font-semibold text-purple-text">₱{totals.spent.toFixed(2)}</span> of ₱{allowance.toFixed(2)}
            </p>
          </div>
          <div className="space-y-2">
            {[
              { label: 'Allowance', value: allowance, color: 'text-purple-primary-light' },
              { label: 'Remaining', value: totals.remaining, color: totals.remaining < 0 ? 'text-red-400' : 'text-emerald-400' },
              { label: 'Days logged', value: `${Object.keys(expenses).length}/7`, color: 'text-purple-text' },
            ].map(({ label: l, value, color }) => (
              <div key={l} className={`${cardInner} flex items-center justify-between px-4 py-3`}>
                <span className={statLabel}>{l}</span>
                <span className={`text-sm font-semibold ${color}`}>
                  {typeof value === 'number' ? `₱${value.toFixed(2)}` : value}
                </span>
              </div>
            ))}
          </div>
          {totals.remaining < 0 && (
            <p className="mt-3 text-center text-xs font-medium text-red-400">Over budget</p>
          )}
        </div>

        <div className="space-y-5">
          {totals.spent > 0 && (
            <div className={`${card} p-5`}>
              <SectionTitle
                className="mb-4"
                right={<span className="text-sm font-semibold text-purple-primary-light">₱{totals.spent.toFixed(2)}</span>}
              >
                Spending this week
              </SectionTitle>
              <MiniBars data={DAYS.map((d) => ({ label: d, short: d.slice(0, 2), value: expenses[d]?.total || 0 }))} />
            </div>
          )}

          <div className={`${card} p-5`}>
            <SectionTitle className="mb-4">Log expense</SectionTitle>
            <p className={`mb-2.5 ${statLabel}`}>Select day</p>
            <div className="mb-5 grid grid-cols-7 gap-1.5">
              {DAYS.map((day, i) => {
                const disabled = i > today;
                const active = selDay === day;
                const isToday = i === today;
                return (
                  <button
                    key={day}
                    type="button"
                    className={`relative flex items-center justify-center rounded-lg py-2 text-xs font-medium transition ${
                      active
                        ? 'bg-purple-primary text-white shadow-glow'
                        : disabled
                          ? 'cursor-not-allowed text-purple-muted/40'
                          : `bg-purple-deep/60 text-purple-soft hover:bg-purple-primary/20 hover:text-purple-text ${isToday ? 'ring-1 ring-inset ring-purple-primary/50' : ''}`
                    }`}
                    onClick={() => selectDay(day, i)}
                    disabled={disabled}
                  >
                    {day.slice(0, 3)}
                  </button>
                );
              })}
            </div>

            {selDay && (
              <div className={`${cardInner} space-y-4 p-4`}>
                <p className={subtext}>
                  Adding for <span className="font-medium text-purple-primary-light">{selDay}</span>
                </p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_110px_auto]">
                  <div>
                    <label className={label}>Item</label>
                    <input type="text" className={input} placeholder="Jeepney fare, lunch…" value={itemName} onChange={(e) => setItemName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addItem()} />
                  </div>
                  <div>
                    <label className={label}>Amount</label>
                    <input type="number" className={input} placeholder="0" min="0" step="0.01" value={itemAmount} onChange={(e) => setItemAmount(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addItem()} />
                  </div>
                  <div className="flex items-end">
                    <button type="button" className={`${btnPrimary} w-full sm:w-auto`} onClick={addItem} disabled={adding}>
                      {adding ? '…' : 'Add'}
                    </button>
                  </div>
                </div>

                {itemName.trim() && (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-purple-muted">Category</span>
                    <CategoryBadge category={category} />
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="rounded-lg border border-purple-primary/15 bg-purple-deep/60 px-2 py-1 text-xs text-purple-text-dim"
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                      ))}
                    </select>
                  </div>
                )}

                {dayItems.length > 0 && (
                  <div className="space-y-2">
                    <p className={statLabel}>Items</p>
                    {dayItems.map((item) => (
                      <div key={item.id} className="flex items-center justify-between rounded-xl bg-purple-deep/40 px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <CategoryBadge category={item.category} />
                          <span className="text-sm text-purple-text-dim">{item.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-medium text-purple-primary-light">₱{item.amount.toFixed(2)}</span>
                          <button type="button" className="text-xs text-purple-muted transition hover:text-red-400" onClick={() => deleteItem(item.id)}>✕</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-purple-primary/10 pt-3 text-xs text-purple-muted">
                  {CATEGORIES.filter((c) => (dayTotals[c] || 0) > 0).map((c) => (
                    <span key={c}>{CATEGORY_LABELS[c]} ₱{(dayTotals[c] || 0).toFixed(2)}</span>
                  ))}
                  <span className="ml-auto font-semibold text-purple-text">₱{(dayTotals.total || 0).toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          {expenseRows.length > 0 && (
            <div className={`${card} p-5`}>
              <SectionTitle className="mb-4">Weekly summary</SectionTitle>
              <div className="mb-5 space-y-2">
                {expenseRows.map(({ day, e, isToday }) => (
                  e ? (
                    <button
                      key={day}
                      type="button"
                      onClick={() => setModalDay(day)}
                      className={`${cardInner} w-full p-4 text-left transition hover:border-purple-primary/30`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 text-sm font-medium text-purple-text">
                          {day}
                          {isToday && <span className="rounded-full bg-purple-primary/20 px-2 py-0.5 text-[10px] font-medium text-purple-primary-light">today</span>}
                        </span>
                        <span className="flex items-center gap-2.5">
                          {e.items?.length > 0 && (
                            <span className="rounded-full bg-purple-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-purple-primary-light">{e.items.length}</span>
                          )}
                          <span className="font-semibold text-purple-primary-light">₱{e.total.toFixed(2)}</span>
                          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 text-purple-muted" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 6l6 6-6 6" />
                          </svg>
                        </span>
                      </div>
                      {CATEGORIES.some((c) => (e[c] || 0) > 0) && (
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {CATEGORIES
                            .filter((c) => (e[c] || 0) > 0)
                            .map((c) => <CategoryBadge key={c} category={c} />)}
                        </div>
                      )}
                    </button>
                  ) : (
                    <div key={day} className="flex items-center justify-between rounded-xl border border-dashed border-purple-primary/10 px-4 py-2.5 text-sm text-purple-muted/50">
                      <span>{day}</span>
                      <span className="text-xs italic">No expenses</span>
                    </div>
                  )
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2 border-t border-purple-primary/10 pt-4 sm:grid-cols-3">
                {CATEGORIES.filter((c) => (totals[c] || 0) > 0).map((c) => (
                  <div key={c} className={`${cardInner} flex items-center justify-between gap-2 px-3 py-2.5`}>
                    <CategoryBadge category={c} />
                    <span className="text-sm font-semibold text-purple-text">₱{(totals[c] || 0).toFixed(2)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between rounded-xl bg-purple-primary/10 px-4 py-3">
                <span className="text-sm font-medium text-purple-soft">Total spent</span>
                <span className="text-lg font-semibold text-purple-primary-light">₱{totals.spent.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {modalDay && expenses[modalDay] && (
        <DayDetailModal
          day={modalDay}
          expense={expenses[modalDay]}
          isToday={DAYS[today] === modalDay}
          onDeleteItem={deleteItem}
          onDeleteDay={deleteDay}
          onClose={() => setModalDay(null)}
        />
      )}
    </div>
  );
}

function DayDetailModal({ day, expense, isToday, onDeleteItem, onDeleteDay, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const items = expense?.items || [];
  const total = expense?.total || 0;
  const grouped = CATEGORIES
    .map((c) => ({ category: c, items: items.filter((it) => it.category === c) }))
    .filter((g) => g.items.length > 0);

  return createPortal(
    <div
      className="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
      style={{ animation: 'fadeIn 0.2s ease-out' }}
    >
      <div
        className={`${card} flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-b-none rounded-t-3xl sm:rounded-3xl`}
        onClick={(e) => e.stopPropagation()}
        style={{ animation: 'fadeIn 0.28s cubic-bezier(0.16,1,0.3,1)' }}
      >
        <div className="flex items-start justify-between gap-4 border-b border-purple-primary/10 px-6 py-5">
          <div>
            <p className={statLabel}>Day detail</p>
            <h3 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-purple-text">
              {day}
              {isToday && <span className="rounded-full bg-purple-primary/20 px-2 py-0.5 text-[10px] font-medium text-purple-primary-light">today</span>}
            </h3>
            <p className="mt-0.5 text-xs text-purple-muted">
              {items.length} {items.length === 1 ? 'item' : 'items'} · ₱{total.toFixed(2)}
            </p>
          </div>
          <button
            type="button"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-purple-muted transition hover:bg-purple-primary/10 hover:text-purple-text"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="no-scrollbar space-y-5 overflow-y-auto px-6 py-5">
          {grouped.length === 0 ? (
            <p className={`py-10 text-center ${subtext}`}>No expenses for this day</p>
          ) : (
            grouped.map(({ category: c, items: its }) => {
              const sub = its.reduce((s, it) => s + it.amount, 0);
              return (
                <div key={c}>
                  <div className="mb-2 flex items-center justify-between">
                    <CategoryBadge category={c} />
                    <span className="text-xs font-medium text-purple-muted">₱{sub.toFixed(2)}</span>
                  </div>
                  <div className="space-y-1.5">
                    {its.map((item) => (
                      <div key={item.id} className={`${cardInner} flex items-center justify-between gap-3 px-3 py-2.5`}>
                        <span className="truncate text-sm text-purple-text-dim">{item.name}</span>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="text-sm font-medium text-purple-primary-light">₱{item.amount.toFixed(2)}</span>
                          <button
                            type="button"
                            className="text-xs text-purple-muted transition hover:text-red-400"
                            onClick={() => onDeleteItem(item.id)}
                            aria-label="Remove item"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-purple-primary/10 px-6 py-4">
          <button
            type="button"
            className="text-xs font-medium text-purple-muted transition hover:text-red-400"
            onClick={() => onDeleteDay(day)}
          >
            Delete day
          </button>
          <span className="text-base font-semibold text-purple-text">Total ₱{total.toFixed(2)}</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function WeekDetailModal({ weekStart, weekLabel, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDays, setOpenDays] = useState(() => new Set());

  const toggleDay = (day) =>
    setOpenDays((prev) => {
      const next = new Set(prev);
      next.has(day) ? next.delete(day) : next.add(day);
      return next;
    });

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    apiFetch(`/api/week-detail?week_start=${encodeURIComponent(weekStart)}`)
      .then((r) => r.json())
      .then((d) => {
        if (!active) return;
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch(() => active && setError('Could not load this week'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [weekStart]);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const allowance = data?.allowance || 0;
  const spent = data?.totals?.spent || 0;
  const remaining = data?.totals?.remaining || 0;
  const pct = allowance ? (spent / allowance) * 100 : 0;
  const barColor = pct > 100 ? 'bg-red-400' : pct > 80 ? 'bg-amber-400' : 'bg-purple-primary';

  const dayRows = DAYS.map((day) => {
    const e = data?.expenses?.[day];
    return { day, total: e?.total || 0, items: e?.items || [] };
  });
  const maxDay = Math.max(1, ...dayRows.map((d) => d.total));
  const loggedDays = dayRows.filter((d) => d.total > 0).length;

  let running = 0;

  return createPortal(
    <div
      className="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
      style={{ animation: 'fadeIn 0.2s ease-out' }}
    >
      <div
        className={`${card} flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-b-none rounded-t-3xl sm:rounded-3xl`}
        onClick={(e) => e.stopPropagation()}
        style={{ animation: 'fadeIn 0.28s cubic-bezier(0.16,1,0.3,1)' }}
      >
        <div className="flex items-start justify-between gap-4 border-b border-purple-primary/10 px-6 py-5">
          <div>
            <p className={statLabel}>Week detail</p>
            <h3 className="text-lg font-semibold tracking-tight text-purple-text">{weekLabel}</h3>
            {data && (
              <p className="mt-0.5 text-xs text-purple-muted">
                {data.week_start_formatted} – {data.week_end_formatted}
              </p>
            )}
          </div>
          <button
            type="button"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-purple-muted transition hover:bg-purple-primary/10 hover:text-purple-text"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="no-scrollbar overflow-y-auto px-6 py-5">
          {loading && (
            <div className="flex justify-center py-16">
              <div className="h-8 w-8 rounded-full border-2 border-purple-primary/30 border-t-purple-primary login-spinner" />
            </div>
          )}

          {!loading && error && (
            <p className={`py-16 text-center ${subtext}`}>{error}</p>
          )}

          {!loading && !error && data && (
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Allowance', value: allowance, color: 'text-purple-primary-light' },
                  { label: 'Spent', value: spent, color: 'text-purple-text' },
                  { label: 'Saved', value: remaining, color: remaining < 0 ? 'text-red-400' : 'text-emerald-400' },
                ].map(({ label: l, value, color }) => (
                  <div key={l} className={`${cardInner} p-4 text-center`}>
                    <p className={statLabel}>{l}</p>
                    <p className={`mt-1 text-base font-semibold sm:text-lg ${color}`}>₱{value.toFixed(2)}</p>
                  </div>
                ))}
              </div>

              <div>
                <div className="mb-1.5 flex justify-between text-xs text-purple-muted">
                  <span>Budget used</span>
                  <span className={pct > 100 ? 'text-red-400' : ''}>{pct.toFixed(0)}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-purple-deep">
                  <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-purple-muted">
                  {CATEGORIES.filter((c) => (data.totals[c] || 0) > 0).map((c) => (
                    <span key={c}>{CATEGORY_LABELS[c]} ₱{(data.totals[c] || 0).toFixed(2)}</span>
                  ))}
                  <span className="ml-auto">{loggedDays}/7 days logged</span>
                </div>
              </div>

              <div>
                <SectionTitle className="mb-3">Daily progress</SectionTitle>
                {loggedDays === 0 ? (
                  <p className={`py-8 text-center ${subtext}`}>No expenses logged this week</p>
                ) : (
                  <div className="space-y-3">
                    {dayRows.map(({ day, total, items }) => {
                      running += total;
                      const cumPct = allowance ? Math.min((running / allowance) * 100, 100) : 0;
                      const hasItems = items.length > 0;
                      const open = openDays.has(day);
                      const runningAtDay = running;
                      return (
                        <div key={day} className={`${cardInner} p-3.5`}>
                          <button
                            type="button"
                            onClick={() => hasItems && toggleDay(day)}
                            className={`flex w-full items-center justify-between gap-3 text-left ${hasItems ? 'cursor-pointer' : 'cursor-default'}`}
                            aria-expanded={open}
                          >
                            <span className="flex w-14 shrink-0 items-center gap-1 text-xs font-medium text-purple-soft">
                              <svg
                                viewBox="0 0 24 24"
                                className={`h-3 w-3 transition-transform duration-200 ${hasItems ? 'text-purple-muted' : 'text-transparent'} ${open ? 'rotate-90' : ''}`}
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              >
                                <path d="M9 6l6 6-6 6" />
                              </svg>
                              {day.slice(0, 3)}
                            </span>
                            <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-purple-deep/70">
                              <span
                                className={`block h-full rounded-full transition-all duration-700 ${total > 0 ? 'bg-purple-primary' : ''}`}
                                style={{ width: `${(total / maxDay) * 100}%` }}
                              />
                            </span>
                            <span className="flex w-24 shrink-0 items-center justify-end gap-1.5">
                              {hasItems && (
                                <span className="rounded-full bg-purple-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-purple-primary-light">
                                  {items.length}
                                </span>
                              )}
                              <span className={`text-sm font-semibold ${total > 0 ? 'text-purple-primary-light' : 'text-purple-muted/50'}`}>
                                ₱{total.toFixed(2)}
                              </span>
                            </span>
                          </button>
                          {hasItems && open && (
                            <div className="mt-3 space-y-2 border-t border-purple-primary/10 pl-14 pt-3">
                              {items.map((item) => (
                                <div key={item.id} className="flex items-center justify-between gap-2 text-xs">
                                  <span className="flex min-w-0 items-center gap-2">
                                    <CategoryBadge category={item.category} />
                                    <span className="truncate text-purple-soft">{item.name}</span>
                                  </span>
                                  <span className="shrink-0 text-purple-text-dim">₱{item.amount.toFixed(2)}</span>
                                </div>
                              ))}
                              <div className="pt-0.5 text-right text-[11px] text-purple-muted">
                                Running total ₱{runningAtDay.toFixed(2)} · {cumPct.toFixed(0)}% of budget
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function MonthlyTab({ initMonth, initYear }) {
  const [month, setMonth] = useState(initMonth);
  const [year, setYear] = useState(initYear);
  const [data, setData] = useState(null);
  const [selectedWeek, setSelectedWeek] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch(`/api/monthly-summary?month=${month}&year=${year}`);
      setData(await r.json());
    } catch {  }
  }, [month, year]);

  useEffect(() => { load(); }, [load]);

  const prev = () => {
    if (month === 1) { setMonth(12); setYear((y) => y - 1); }
    else setMonth((m) => m - 1);
  };
  const next = () => {
    if (month === 12) { setMonth(1); setYear((y) => y + 1); }
    else setMonth((m) => m + 1);
  };

  return (
    <div className={`${card} p-6`}>
      {selectedWeek && (
        <WeekDetailModal
          weekStart={selectedWeek.week_start}
          weekLabel={selectedWeek.label}
          onClose={() => setSelectedWeek(null)}
        />
      )}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <SectionTitle>Monthly summary</SectionTitle>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-xl border border-purple-primary/15 bg-purple-deep/40 p-1">
            <button type="button" className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text" onClick={prev} aria-label="Previous month">←</button>
            <span className="min-w-[120px] text-center text-sm font-medium text-purple-text">{data?.month_name || '…'}</span>
            <button type="button" className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text" onClick={next} aria-label="Next month">→</button>
          </div>
          <button type="button" className={btnPrimary} onClick={() => openPdf(`/api/export-monthly-pdf?month=${month}&year=${year}`)}>
            PDF
          </button>
        </div>
      </div>

      {!data || data.num_weeks === 0 ? (
        <p className={`py-12 text-center ${subtext}`}>No data for this month</p>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-1 gap-5 lg:grid-cols-[210px_1fr]">
            <div className={`${cardInner} flex flex-col items-center justify-center p-5`}>
              <RingProgress value={data.total_allowance ? (data.total_spent / data.total_allowance) * 100 : 0} />
              <p className="mt-3 text-xs text-purple-muted">Monthly budget used</p>
              <p className={`mt-1 text-sm font-semibold ${data.total_saved < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                {data.total_saved < 0 ? 'Over by ' : 'Saved '}₱{Math.abs(data.total_saved).toFixed(2)}
              </p>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  { label: 'Allowance', value: data.total_allowance, accent: 'bg-purple-primary', text: 'text-purple-primary-light' },
                  { label: 'Spent', value: data.total_spent, accent: 'bg-fuchsia-400', text: 'text-purple-primary-light' },
                  { label: 'Saved', value: data.total_saved, accent: data.total_saved < 0 ? 'bg-red-400' : 'bg-emerald-400', text: data.total_saved < 0 ? 'text-red-400' : 'text-emerald-400' },
                ].map(({ label: l, value, text, accent }) => (
                  <div key={l} className={`${cardInner} relative overflow-hidden p-4`}>
                    <span className={`absolute inset-x-0 top-0 h-1 ${accent}`} />
                    <p className={statLabel}>{l}</p>
                    <p className={`mt-1 text-xl font-semibold tracking-tight ${text}`}>
                      ₱{value.toFixed(2)}
                    </p>
                  </div>
                ))}
              </div>
              <div className={`${cardInner} p-4`}>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-medium text-purple-text">Spending by week</p>
                  <span className="text-xs text-purple-muted">₱{data.total_spent.toFixed(2)} total</span>
                </div>
                <MiniBars data={data.weeks.map((w, i) => ({ label: `Week ${i + 1}`, short: `W${i + 1}`, value: w.spent }))} height={80} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div>
              <SectionTitle className="mb-3">Breakdown</SectionTitle>
              <div className="space-y-2">
                {CATEGORIES.filter((c) => (data.breakdown[c] || 0) > 0).length === 0 ? (
                  <p className={`py-6 text-center ${subtext}`}>No expenses this month</p>
                ) : (
                  CATEGORIES.filter((c) => (data.breakdown[c] || 0) > 0).map((c) => (
                    <div key={c} className={`${cardInner} flex items-center justify-between px-4 py-3`}>
                      <CategoryBadge category={c} />
                      <span className="text-sm font-medium text-purple-text">₱{(data.breakdown[c] || 0).toFixed(2)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
            <div>
              <SectionTitle
                className="mb-3"
                right={<span className="text-xs text-purple-muted">Tap a week for details</span>}
              >
                By week
              </SectionTitle>
              <div className="space-y-2">
                {data.weeks.map((w, i) => {
                  const date = new Date(w.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                  const pct = w.allowance ? Math.min((w.spent / w.allowance) * 100, 100) : 0;
                  const barColor = w.spent > w.allowance ? 'bg-red-400' : pct > 80 ? 'bg-amber-400' : 'bg-purple-primary';
                  const weekLabel = `Week ${i + 1}`;
                  return (
                    <button
                      key={w.week_start}
                      type="button"
                      onClick={() => setSelectedWeek({ week_start: w.week_start, label: weekLabel })}
                      className={`${cardInner} group w-full p-4 text-left transition hover:border-purple-primary/30 hover:bg-purple-primary/10 focus:outline-none focus:ring-2 focus:ring-purple-primary/30`}
                    >
                      <div className="mb-2 flex items-center justify-between">
                        <span className="flex items-center gap-2 text-sm font-medium text-purple-text">
                          {weekLabel}
                          <span className="text-purple-muted transition group-hover:translate-x-0.5 group-hover:text-purple-primary-light">›</span>
                        </span>
                        <span className="text-xs text-purple-muted">{date}</span>
                      </div>
                      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-purple-deep">
                        <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${pct}%` }} />
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div><p className="text-purple-muted">Allowance</p><p className="font-medium text-purple-text-dim">₱{w.allowance.toFixed(0)}</p></div>
                        <div><p className="text-purple-muted">Spent</p><p className="font-medium text-purple-text-dim">₱{w.spent.toFixed(0)}</p></div>
                        <div><p className="text-purple-muted">Saved</p><p className={`font-medium ${w.saved >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>₱{w.saved.toFixed(0)}</p></div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function Dashboard() {
  const now = new Date();
  const navigate = useNavigate();
  const [tab, setTab] = useState('weekly');
  const [screen, setScreen] = useState('setup');
  const [username, setUsername] = useState('');
  const [darkMode, setDarkMode] = useState(localStorage.getItem('darkMode') !== 'false');
  const [menuOpen, setMenuOpen] = useState(false);
  const [weekInfo, setWeekInfo] = useState(null);
  const [allowance, setAllowance] = useState(0);
  const [expenses, setExpenses] = useState({});
  const [totals, setTotals] = useState({ fare: 0, food: 0, other: 0, spent: 0, remaining: 0 });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const toggleTheme = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('darkMode', next);
  };

  const logout = async () => {
    await apiFetch('/api/logout', { method: 'POST' });
    navigate('/');
  };

  const refreshBudget = useCallback(async () => {
    try {
      const r = await apiFetch('/api/get-budget');
      const d = await r.json();
      if (d.allowance > 0) {
        setAllowance(d.allowance);
        setExpenses(d.expenses || {});
        setTotals(d.totals);
        setScreen('tracker');
      }
    } catch {  }
  }, []);

  useEffect(() => {
    apiFetch('/api/check-auth')
      .then((r) => r.json())
      .then((d) => {
        if (!d.authenticated) { navigate('/'); return; }
        setUsername(d.username);
      })
      .catch(() => navigate('/'));
    apiFetch('/api/current-week-info').then((r) => r.json()).then(setWeekInfo).catch(() => {});
    refreshBudget();
  }, [navigate, refreshBudget]);

  const handleStart = (n) => {
    setAllowance(n);
    setScreen('tracker');
    refreshBudget();
  };

  const tabCls = (active) =>
    `flex-1 rounded-xl px-5 py-2.5 text-center text-sm font-medium transition ${
      active
        ? 'bg-purple-primary text-white shadow-glow'
        : 'text-purple-soft hover:bg-purple-primary/10 hover:text-purple-text'
    }`;

  return (
    <div className="mx-auto max-w-5xl">
      <MobileMenu
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        darkMode={darkMode}
        onTheme={toggleTheme}
        showExport={screen === 'tracker'}
        onExport={() => openPdf('/api/export-pdf')}
        onLogout={logout}
        currentMonth={now.getMonth() + 1}
        currentYear={now.getFullYear()}
      />

      <header className="mb-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-primary to-purple-primary-light shadow-glow ring-1 ring-inset ring-white/15">
            <span className="text-base font-semibold leading-none text-white">₱</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight tracking-tight text-purple-text">Budget Tracker</h1>
            <p className="text-xs text-purple-muted">Master your finances with style</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {username && <span className="mr-1 hidden text-sm text-purple-soft md:inline">Hi, {username}</span>}
          <IconButton className="inline-flex sm:hidden" label="Menu" onClick={() => setMenuOpen(true)}>
            <MenuIcon />
          </IconButton>
          <IconButton className="hidden sm:inline-flex" label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'} onClick={toggleTheme}>
            {darkMode ? <SunIcon /> : <MoonIcon />}
          </IconButton>
          {screen === 'tracker' && (
            <IconButton className="hidden sm:inline-flex" label="Export PDF" onClick={() => openPdf('/api/export-pdf')}>
              <ExportIcon />
            </IconButton>
          )}
          <IconButton danger className="hidden sm:inline-flex" label="Logout" onClick={logout}>
            <LogoutIcon />
            <span className="hidden lg:inline">Logout</span>
          </IconButton>
        </div>
      </header>

      <nav className="mb-6 flex gap-1.5 rounded-2xl border border-purple-primary/10 bg-purple-surface/40 p-1.5 shadow-card backdrop-blur">
        <button type="button" className={tabCls(tab === 'weekly')} onClick={() => setTab('weekly')}>Weekly Budget</button>
        <button type="button" className={tabCls(tab === 'monthly')} onClick={() => setTab('monthly')}>Monthly Summary</button>
      </nav>

      {tab === 'weekly' && (
        screen === 'setup'
          ? <SetupScreen weekInfo={weekInfo} onStart={handleStart} />
          : (
            <WeeklyTracker
              weekInfo={weekInfo}
              allowance={allowance}
              expenses={expenses}
              totals={totals}
              onRefresh={refreshBudget}
            />
          )
      )}
      {tab === 'monthly' && (
        <MonthlyTab initMonth={now.getMonth() + 1} initYear={now.getFullYear()} />
      )}
    </div>
  );
}

