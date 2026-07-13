import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { apiFetch, openPdf, primeCsrf, downloadCsv, runExport } from '../api';
import { applyMutationPatch, applyDashboardData, patchComparisonFromTotals, patchAllowance } from '../utils/budgetPatch';
import { CategoryDonutChart, WeekComparisonChart, SpendingByDayChart } from '../components/BudgetCharts';
import UndoToast from '../components/UndoToast';
import CategoryBadge from '../components/CategoryBadge';
import { useCategories } from '../components/CategoriesContext';
import ShortcutsHelp, { isEditableTarget } from '../components/ShortcutsHelp';
import {
  categorizeItem,
  categoryLabel,
} from '../utils/categorize';
import {
  card, cardInner, input, label, btnPrimary,
  heading, subtext, statLabel,
} from '../utils/theme';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function tagsToInput(tags) {
  return Array.isArray(tags) ? tags.join(', ') : (tags || '');
}

function ItemMeta({ notes, tags }) {
  const hasNotes = Boolean(notes?.trim());
  const list = Array.isArray(tags) ? tags.filter(Boolean) : [];
  if (!hasNotes && !list.length) return null;
  return (
    <div className="mt-1 space-y-1">
      {hasNotes && <p className="text-xs text-purple-muted">{notes}</p>}
      {list.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {list.map((tag) => (
            <span
              key={tag}
              className="rounded-md bg-purple-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-purple-primary-light"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const ICON = 'h-[18px] w-[18px]';
const svgProps = {
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', className: ICON,
};

const ExportIcon = () => (
  <svg {...svgProps}>
    <path d="M12 3v12" /><path d="m8 11 4 4 4-4" /><path d="M20 17v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2" />
  </svg>
);
const CsvIcon = () => (
  <svg {...svgProps}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h8" /><path d="M8 9h2" />
  </svg>
);
const EditIcon = () => (
  <svg {...svgProps} className="h-4 w-4">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
);

function IconButton({ onClick, label, danger, className = '', children }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl border h-10 px-3 text-sm font-medium transition active:scale-[0.97]';
  const tone = danger
    ? 'border-red-400/25 bg-red-500/10 text-red-300 hover:bg-red-500/20 light:border-red-200 light:bg-white light:text-red-600 light:shadow-sm light:hover:bg-red-50'
    : 'glass-btn-ghost h-10 px-3 text-sm font-medium text-purple-text-dim hover:text-purple-text';
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label} className={`${base} ${tone} ${className}`}>
      {children}
    </button>
  );
}

function EditableAllowanceRow({ allowance, onSave }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState('');
  const [saving, setSaving] = useState(false);

  const start = () => {
    setVal(String(allowance));
    setEditing(true);
  };

  const cancel = () => setEditing(false);

  const save = async () => {
    const n = parseFloat(val);
    if (!n || n <= 0) return alert('Enter a valid allowance');
    setSaving(true);
    try {
      await onSave(n);
      setEditing(false);
    } catch {
      alert('Failed to update allowance');
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className={`${cardInner} space-y-2 px-4 py-3`}>
        <label className={statLabel}>Weekly allowance</label>
        <div className="flex flex-wrap gap-2">
          <input
            type="number"
            className={`${input} min-w-[120px] flex-1`}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            min="0"
            step="0.01"
            onKeyDown={(e) => e.key === 'Enter' && save()}
          />
          <button type="button" className={`${btnPrimary} px-3 py-2 text-xs`} onClick={save} disabled={saving}>
            {saving ? '…' : 'Save'}
          </button>
          <button type="button" className="px-2 py-2 text-xs text-purple-muted hover:text-purple-text" onClick={cancel}>
            Cancel
          </button>
        </div>
        <p className="text-[10px] text-purple-muted">Update if you receive extra allowance mid-week</p>
      </div>
    );
  }

  return (
    <div className={`${cardInner} flex items-center justify-between px-4 py-3`}>
      <span className={statLabel}>Allowance</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-purple-primary-light">₱{allowance.toFixed(2)}</span>
        <button
          type="button"
          className="inline-flex text-purple-muted transition hover:text-purple-primary-light"
          onClick={start}
          aria-label="Edit allowance"
          title="Edit allowance"
        >
          <EditIcon />
        </button>
      </div>
    </div>
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
            {weekInfo.week_start_formatted} to {weekInfo.week_end_formatted}
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

function daysLeftInWeek(weekInfo) {
  if (!weekInfo) return 1;
  return Math.max(weekInfo.days_remaining, 1);
}

function formatDelta(amount) {
  const sign = amount > 0 ? '+' : amount < 0 ? '−' : '';
  return `${sign}₱${Math.abs(amount).toFixed(2)}`;
}

function WeekComparisonCard({ data }) {
  if (!data?.current) return null;

  const { current, previous, delta } = data;
  const hasLastWeek = previous.has_budget;
  const spentUp = delta.spent > 0;
  const spentDown = delta.spent < 0;
  const deltaTone = spentUp
    ? 'text-amber-300'
    : spentDown
      ? 'text-emerald-300'
      : 'text-purple-muted';

  return (
    <div className={`${card} p-5`}>
      <SectionTitle className="mb-4">This week vs last week</SectionTitle>
      <div className="grid grid-cols-2 gap-3">
        <div className={`${cardInner} px-4 py-3`}>
          <p className={statLabel}>This week</p>
          <p className="mt-1 text-lg font-semibold text-purple-text">₱{current.spent.toFixed(2)}</p>
          <p className="mt-0.5 text-xs text-purple-muted">of ₱{current.allowance.toFixed(2)}</p>
        </div>
        <div className={`${cardInner} px-4 py-3`}>
          <p className={statLabel}>Last week</p>
          {hasLastWeek ? (
            <>
              <p className="mt-1 text-lg font-semibold text-purple-text">₱{previous.spent.toFixed(2)}</p>
              <p className="mt-0.5 text-xs text-purple-muted">of ₱{previous.allowance.toFixed(2)}</p>
            </>
          ) : (
            <p className="mt-1 text-sm text-purple-muted">No budget logged</p>
          )}
        </div>
      </div>
      {hasLastWeek && (
        <p className={`mt-3 text-center text-sm font-medium ${deltaTone}`}>
          {formatDelta(delta.spent)} spent vs last week
          {delta.spent_pct_change != null && (
            <span className="text-purple-muted">
              {' '}({delta.spent_pct_change > 0 ? '+' : ''}{delta.spent_pct_change}%)
            </span>
          )}
        </p>
      )}
    </div>
  );
}

function CategoryLimitAlerts({ categoryStatus }) {
  const { categories, labels } = useCategories();
  if (!categoryStatus) return null;

  const over = categories.filter((c) => categoryStatus[c]?.over);
  const warning = categories.filter((c) => categoryStatus[c]?.warning && !categoryStatus[c]?.over);

  if (!over.length && !warning.length) return null;

  return (
    <div className="space-y-2">
      {over.map((c) => (
        <div key={c} className="rounded-xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          <span className="font-medium">{categoryLabel(c, labels)}</span>
          {' '}is over limit at ₱{categoryStatus[c].spent.toFixed(2)} of ₱{categoryStatus[c].limit.toFixed(2)}
        </div>
      ))}
      {warning.map((c) => (
        <div key={c} className="rounded-xl border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <span className="font-medium">{categoryLabel(c, labels)}</span>
          {' '}at {categoryStatus[c].pct}% of limit (₱{categoryStatus[c].spent.toFixed(2)} / ₱{categoryStatus[c].limit.toFixed(2)})
        </div>
      ))}
    </div>
  );
}

function CategoryLimitRow({ category, spent, status }) {
  if (!status?.limit) return null;
  const pct = Math.min(status.pct || 0, 100);
  const barColor = status.over ? 'bg-red-400' : pct >= 80 ? 'bg-amber-400' : 'bg-purple-primary';
  return (
    <div className="glass-track mt-1.5 h-1.5 overflow-hidden rounded-full">
      <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function WeeklyTracker({
  weekInfo, allowance, expenses, totals, comparison, categoryStatus, categoryRules,
  onBudgetPatch, onAllowanceChange, onItemDeleted,
}) {
  const { categories, labels } = useCategories();
  const today = new Date().getDay();
  const [selDay, setSelDay] = useState(DAYS[today]);
  const [itemName, setItemName] = useState('');
  const [itemAmount, setItemAmount] = useState('');
  const [itemNotes, setItemNotes] = useState('');
  const [itemTags, setItemTags] = useState('');
  const [category, setCategory] = useState('other');
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editTags, setEditTags] = useState('');
  const [editCategory, setEditCategory] = useState('other');
  const [savingEdit, setSavingEdit] = useState(false);
  const [modalDay, setModalDay] = useState(null);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const logExpenseRef = useRef(null);
  const itemNameRef = useRef(null);
  const itemAmountRef = useRef(null);

  useEffect(() => {
    if (itemName.trim()) setCategory(categorizeItem(itemName, categoryRules, categories));
  }, [itemName, categoryRules, categories]);

  const clearForm = () => {
    setItemName('');
    setItemAmount('');
    setItemNotes('');
    setItemTags('');
    setCategory('other');
  };

  const focusNewExpense = () => {
    if (!selDay) setSelDay(DAYS[today]);
    requestAnimationFrame(() => {
      logExpenseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      itemNameRef.current?.focus();
    });
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.defaultPrevented) return;
      const typing = isEditableTarget(e.target);
      const metaEnter = (e.metaKey || e.ctrlKey) && e.key === 'Enter';

      if (e.key === '?' && !typing) {
        e.preventDefault();
        setShortcutsOpen((open) => !open);
        return;
      }

      if (shortcutsOpen) return;

      if (e.key === 'Escape') {
        if (modalDay) {
          setModalDay(null);
          return;
        }
        if (editingId) {
          cancelEdit();
          return;
        }
        if (typing) {
          e.target.blur?.();
          clearForm();
        }
        return;
      }

      if (metaEnter && !adding && !editingId) {
        e.preventDefault();
        addItem();
        return;
      }

      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;

      const key = e.key.toLowerCase();
      if (key === 'n') {
        e.preventDefault();
        focusNewExpense();
        return;
      }
      if (key === 'a') {
        e.preventDefault();
        logExpenseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        itemAmountRef.current?.focus();
        return;
      }
      if (key >= '1' && key <= '7') {
        const index = Number(key) - 1;
        if (index <= today) {
          e.preventDefault();
          selectDay(DAYS[index], index);
          focusNewExpense();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    adding, editingId, modalDay, shortcutsOpen, selDay, today,
    itemName, itemAmount, itemNotes, itemTags, category,
  ]);

  const selectDay = (day, i) => {
    if (i > today) return;
    setSelDay(day);
    setEditingId(null);
    clearForm();
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
        body: JSON.stringify({
          day: selDay,
          name,
          amount,
          category,
          notes: itemNotes,
          tags: itemTags,
        }),
      });
      if (r.ok) {
        const d = await r.json();
        clearForm();
        onBudgetPatch(d);
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

  const deleteItem = async (item) => {
    try {
      const r = await apiFetch(`/api/delete-expense-item/${item.id}`, { method: 'DELETE' });
      if (r.ok) {
        const d = await r.json();
        if (editingId === item.id) setEditingId(null);
        onBudgetPatch(d);
        if (d.deleted_item && onItemDeleted) {
          onItemDeleted({ ...d.deleted_item, day: d.day || selDay });
        }
      }
    } catch {
      alert('Server error');
    }
  };

  const startEdit = (item, dayForEdit = selDay) => {
    if (dayForEdit) setSelDay(dayForEdit);
    setEditingId(item.id);
    setEditName(item.name);
    setEditAmount(String(item.amount));
    setEditNotes(item.notes || '');
    setEditTags(tagsToInput(item.tags));
    setEditCategory(item.category);
    requestAnimationFrame(() => {
      logExpenseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditAmount('');
    setEditNotes('');
    setEditTags('');
    setEditCategory('other');
  };

  const saveEdit = async (itemId) => {
    const name = editName.trim();
    const amount = parseFloat(editAmount);
    if (!name) return alert('Enter an item name');
    if (!amount || amount <= 0) return alert('Enter a valid amount');
    setSavingEdit(true);
    try {
      const r = await apiFetch(`/api/edit-expense-item/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name,
          amount,
          category: editCategory,
          notes: editNotes,
          tags: editTags,
        }),
      });
      if (r.ok) {
        cancelEdit();
        onBudgetPatch(await r.json());
      } else {
        const d = await r.json();
        alert(d.error || 'Failed to update item');
      }
    } catch {
      alert('Server error');
    } finally {
      setSavingEdit(false);
    }
  };

  const renderExpenseItem = (item) => {
    if (editingId === item.id) {
      return (
        <div key={item.id} className="space-y-3 glass-surface rounded-xl px-3 py-2.5">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_100px]">
            <input type="text" className={input} value={editName} onChange={(e) => setEditName(e.target.value)} />
            <input type="number" className={input} min="0" step="0.01" value={editAmount} onChange={(e) => setEditAmount(e.target.value)} />
          </div>
          <input
            type="text"
            className={input}
            placeholder="e.g. Split with Ana"
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
          />
          <input
            type="text"
            className={input}
            placeholder="e.g. work, gcash"
            value={editTags}
            onChange={(e) => setEditTags(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={editCategory}
              onChange={(e) => setEditCategory(e.target.value)}
              className="glass-input rounded-lg px-2 py-1 text-xs text-purple-text-dim"
            >
              {categories.map((c) => (
                <option key={c} value={c}>{categoryLabel(c, labels)}</option>
              ))}
            </select>
            <button type="button" className={`${btnPrimary} px-3 py-1.5 text-xs`} onClick={() => saveEdit(item.id)} disabled={savingEdit}>
              {savingEdit ? '…' : 'Save'}
            </button>
            <button type="button" className="text-xs text-purple-muted transition hover:text-purple-text" onClick={cancelEdit}>
              Cancel
            </button>
          </div>
        </div>
      );
    }

    return (
      <div key={item.id} className="flex items-start justify-between gap-2 glass-surface rounded-xl px-3 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CategoryBadge category={item.category} />
            <span className="truncate text-sm text-purple-text-dim">{item.name}</span>
          </div>
          <ItemMeta notes={item.notes} tags={item.tags} />
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-0.5">
          <span className="text-sm font-medium text-purple-primary-light">₱{item.amount.toFixed(2)}</span>
          <button type="button" className="inline-flex text-purple-muted transition hover:text-purple-primary-light" onClick={() => startEdit(item)} aria-label="Edit item" title="Edit">
            <EditIcon />
          </button>
          <button type="button" className="text-xs text-purple-muted transition hover:text-red-400" onClick={() => deleteItem(item)} aria-label="Remove item">
            ✕
          </button>
        </div>
      </div>
    );
  };

  const deleteDay = async (day) => {
    if (!confirm(`Delete all expenses for ${day}?`)) return;
    try {
      const r = await apiFetch(`/api/delete-expense/${day}`, { method: 'DELETE' });
      if (r.ok) onBudgetPatch(await r.json());
    } catch {
      alert('Server error');
    }
  };

  const pct = allowance ? (totals.spent / allowance) * 100 : 0;

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
              {weekInfo.week_start_formatted} to {weekInfo.week_end_formatted}
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

      {allowance > 0 && comparison && (
        <WeekComparisonCard data={comparison} />
      )}

      <CategoryLimitAlerts categoryStatus={categoryStatus} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className={`${card} p-5`}>
          <SectionTitle className="mb-4">Overview</SectionTitle>
          <EditableAllowanceRow allowance={allowance} onSave={onAllowanceChange} />
          <div className="my-4 flex flex-col items-center glass-well py-5">
            <RingProgress value={pct} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className={`${cardInner} px-4 py-3`}>
              <p className={statLabel}>Spent</p>
              <p className="mt-1 text-lg font-semibold text-purple-text">₱{totals.spent.toFixed(2)}</p>
            </div>
            <div className={`${cardInner} px-4 py-3`}>
              <p className={statLabel}>Remaining</p>
              <p className={`mt-1 text-lg font-semibold ${totals.remaining < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                ₱{totals.remaining.toFixed(2)}
              </p>
            </div>
          </div>
          <div className={`${cardInner} mt-2 flex items-center justify-between px-4 py-3`}>
            <span className={statLabel}>Days logged</span>
            <span className="text-sm font-semibold text-purple-text">{Object.keys(expenses).length}/7</span>
          </div>
          {totals.remaining < 0 && (
            <p className="mt-3 text-center text-xs font-medium text-red-400">Over budget</p>
          )}
          {weekInfo && totals.remaining > 0 && (
            <p className="mt-3 text-center text-xs text-purple-muted">
              About ₱{(totals.remaining / daysLeftInWeek(weekInfo)).toFixed(2)} per day for {daysLeftInWeek(weekInfo)} day{daysLeftInWeek(weekInfo) === 1 ? '' : 's'} left
            </p>
          )}
        </div>

        <div ref={logExpenseRef} className={`${card} p-5 scroll-mt-6`}>
          <SectionTitle
            className="mb-4"
            right={(
              <button
                type="button"
                onClick={() => setShortcutsOpen(true)}
                className="glass-btn-ghost inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium text-purple-muted hover:text-purple-text"
                title="Keyboard shortcuts (?)"
                aria-label="Keyboard shortcuts"
              >
                <kbd className="rounded border border-purple-primary/25 bg-purple-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-purple-primary-light">?</kbd>
                Shortcuts
              </button>
            )}
          >
            Log expense
          </SectionTitle>
          <p className={`mb-2.5 ${statLabel}`}>Select day <span className="font-normal normal-case tracking-normal text-purple-muted/70">(1–7)</span></p>
          <div className="mb-5 grid grid-cols-7 gap-1.5">
            {DAYS.map((day, i) => {
              const disabled = i > today;
              const active = selDay === day;
              const isToday = i === today;
              return (
                <button
                  key={day}
                  type="button"
                  className={`relative flex items-center justify-center rounded-full py-2 text-xs font-medium transition ${
                    active
                      ? 'bg-purple-primary text-white shadow-glow'
                      : disabled
                        ? 'cursor-not-allowed text-purple-muted/40'
                        : `glass-surface text-purple-soft hover:bg-purple-primary/20 hover:text-purple-text ${isToday ? 'ring-1 ring-inset ring-purple-primary/50' : ''}`
                  }`}
                  onClick={() => selectDay(day, i)}
                  disabled={disabled}
                  title={`${day} (press ${i + 1})`}
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
                <span className="ml-2 text-purple-muted/70">Press <kbd className="rounded border border-purple-primary/20 px-1 font-mono text-[10px]">N</kbd> to focus</span>
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_110px_auto]">
                <div>
                  <label className={label}>Item</label>
                  <input
                    ref={itemNameRef}
                    type="text"
                    className={input}
                    placeholder="Jeepney fare, lunch…"
                    value={itemName}
                    onChange={(e) => setItemName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addItem()}
                  />
                </div>
                <div>
                  <label className={label}>Amount</label>
                  <input
                    ref={itemAmountRef}
                    type="number"
                    className={input}
                    placeholder="0"
                    min="0"
                    step="0.01"
                    value={itemAmount}
                    onChange={(e) => setItemAmount(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addItem()}
                  />
                </div>
                <div className="flex items-end">
                  <button type="button" className={`${btnPrimary} w-full sm:w-auto`} onClick={addItem} disabled={adding}>
                    {adding ? '…' : 'Add'}
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className={label}>Note</label>
                  <input
                    type="text"
                    className={input}
                    placeholder="e.g. Split with Ana"
                    value={itemNotes}
                    onChange={(e) => setItemNotes(e.target.value)}
                  />
                </div>
                <div>
                  <label className={label}>Tags</label>
                  <input
                    type="text"
                    className={input}
                    placeholder="e.g. work, gcash"
                    value={itemTags}
                    onChange={(e) => setItemTags(e.target.value)}
                  />
                </div>
              </div>

              {itemName.trim() && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-purple-muted">Category</span>
                  <CategoryBadge category={category} />
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="glass-input rounded-lg px-2 py-1 text-xs text-purple-text-dim"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>{categoryLabel(c, labels)}</option>
                    ))}
                  </select>
                </div>
              )}

              {dayItems.length > 0 && (
                <div className="space-y-2">
                  <p className={statLabel}>Items</p>
                  {dayItems.map((item) => renderExpenseItem(item))}
                </div>
              )}

              {dayItems.length === 0 && (
                <p className={`text-center text-xs ${subtext}`}>No items for {selDay} yet. Add one above.</p>
              )}

              <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-purple-primary/10 pt-3 text-xs text-purple-muted">
                {categories.filter((c) => (dayTotals[c] || 0) > 0).map((c) => (
                  <span key={c}>{categoryLabel(c, labels)} ₱{(dayTotals[c] || 0).toFixed(2)}</span>
                ))}
                <span className="ml-auto font-semibold text-purple-text">₱{(dayTotals.total || 0).toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {totals.spent === 0 && (
        <div className={`${card} p-5 text-center`}>
          <p className="text-sm font-medium text-purple-text">No expenses yet this week</p>
          <p className={`mt-1 ${subtext}`}>Select a day above and add your first item: fare, food, groceries, and more.</p>
        </div>
      )}

      {totals.spent > 0 && (
        <div className={`${card} p-5`}>
          <SectionTitle className="mb-4">Spending insights</SectionTitle>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <CategoryDonutChart totals={totals} />
            {comparison?.previous?.has_budget ? (
              <WeekComparisonChart comparison={comparison} />
            ) : (
              <div className="glass-inner flex min-h-[200px] items-center justify-center rounded-xl p-4 text-sm text-purple-muted">
                Log a full week to compare with last week
              </div>
            )}
          </div>
          <div className="mt-3">
            <SpendingByDayChart expenses={expenses} todayIndex={today} />
          </div>
        </div>
      )}

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
                  {categories.some((c) => (e[c] || 0) > 0) && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {categories
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
            {categories.filter((c) => (totals[c] || 0) > 0 || categoryStatus?.[c]?.limit).map((c) => (
              <div key={c} className={`${cardInner} px-3 py-2.5`}>
                <div className="flex items-center justify-between gap-2">
                  <CategoryBadge category={c} />
                  <span className="text-sm font-semibold text-purple-text">₱{(totals[c] || 0).toFixed(2)}</span>
                </div>
                {categoryStatus?.[c]?.limit && (
                  <p className="mt-1 text-[10px] text-purple-muted">
                    Limit ₱{categoryStatus[c].limit.toFixed(2)}
                    {categoryStatus[c].over && <span className="ml-1 text-red-400">over</span>}
                  </p>
                )}
                <CategoryLimitRow category={c} spent={totals[c] || 0} status={categoryStatus?.[c]} />
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl bg-purple-primary/10 px-4 py-3">
            <span className="text-sm font-medium text-purple-soft">Total spent</span>
            <span className="text-lg font-semibold text-purple-primary-light">₱{totals.spent.toFixed(2)}</span>
          </div>
        </div>
      )}

      {modalDay && expenses[modalDay] && (
        <DayDetailModal
          day={modalDay}
          expense={expenses[modalDay]}
          isToday={DAYS[today] === modalDay}
          onDeleteItem={deleteItem}
          onEditItem={(item, editDay) => startEdit(item, editDay || modalDay)}
          onDeleteDay={deleteDay}
          onClose={() => setModalDay(null)}
        />
      )}

      <ShortcutsHelp open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}

function DayDetailModal({ day, expense, isToday, onDeleteItem, onEditItem, onDeleteDay, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const { categories } = useCategories();
  const items = expense?.items || [];
  const total = expense?.total || 0;
  const grouped = categories
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
              {items.length} {items.length === 1 ? 'item' : 'items'}, ₱{total.toFixed(2)}
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
                      <div key={item.id} className={`${cardInner} flex items-start justify-between gap-3 px-3 py-2.5`}>
                        <div className="min-w-0">
                          <span className="block truncate text-sm text-purple-text-dim">{item.name}</span>
                          <ItemMeta notes={item.notes} tags={item.tags} />
                        </div>
                        <div className="flex shrink-0 items-center gap-2 pt-0.5">
                          <span className="text-sm font-medium text-purple-primary-light">₱{item.amount.toFixed(2)}</span>
                          <button
                            type="button"
                            className="inline-flex text-purple-muted transition hover:text-purple-primary-light"
                            onClick={() => { onEditItem(item, day); onClose(); }}
                            aria-label="Edit item"
                            title="Edit"
                          >
                            <EditIcon />
                          </button>
                          <button
                            type="button"
                            className="text-xs text-purple-muted transition hover:text-red-400"
                            onClick={() => onDeleteItem(item)}
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
  const { categories, labels } = useCategories();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDays, setOpenDays] = useState(() => new Set());

  const toggleDay = (day) =>
    setOpenDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
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
                {data.week_start_formatted} to {data.week_end_formatted}
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
                <div className="glass-track h-2 overflow-hidden rounded-full">
                  <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-purple-muted">
                  {categories.filter((c) => (data.totals[c] || 0) > 0).map((c) => (
                    <span key={c}>{categoryLabel(c, labels)} ₱{(data.totals[c] || 0).toFixed(2)}</span>
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
                            <span className="glass-track h-2.5 flex-1 overflow-hidden rounded-full">
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
                                Running total ₱{runningAtDay.toFixed(2)}, {cumPct.toFixed(0)}% of budget
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
  const { categories } = useCategories();
  const [month, setMonth] = useState(initMonth);
  const [year, setYear] = useState(initYear);
  const [data, setData] = useState(null);
  const [selectedWeek, setSelectedWeek] = useState(null);
  const loadRef = useRef(null);

  const load = useCallback(async () => {
    if (loadRef.current) return loadRef.current;
    const request = (async () => {
      try {
        const r = await apiFetch(`/api/monthly-summary?month=${month}&year=${year}`);
        setData(await r.json());
      } catch { } finally {
        loadRef.current = null;
      }
    })();
    loadRef.current = request;
    return request;
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
          <div className="glass-inner flex items-center gap-1 rounded-xl p-1">
            <button type="button" className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text" onClick={prev} aria-label="Previous month">←</button>
            <span className="min-w-[120px] text-center text-sm font-medium text-purple-text">{data?.month_name || '…'}</span>
            <button type="button" className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text" onClick={next} aria-label="Next month">→</button>
          </div>
          <IconButton label="Export monthly CSV" onClick={() => runExport(() => downloadCsv(`/api/export-csv?scope=month&month=${month}&year=${year}`))}>
            <CsvIcon />
          </IconButton>
          <IconButton label="Export monthly PDF" onClick={() => runExport(() => openPdf(`/api/export-monthly-pdf?month=${month}&year=${year}`))}>
            <ExportIcon />
          </IconButton>
        </div>
      </div>

      {!data || data.num_weeks === 0 ? (
        <div className="py-12 text-center">
          <p className={`${subtext}`}>No data for this month</p>
          <p className="mt-2 text-xs text-purple-muted">Log expenses in the Weekly tab. Each week rolls up here automatically.</p>
        </div>
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
                {categories.filter((c) => (data.breakdown[c] || 0) > 0).length === 0 ? (
                  <p className={`py-6 text-center ${subtext}`}>No expenses this month</p>
                ) : (
                  categories.filter((c) => (data.breakdown[c] || 0) > 0).map((c) => (
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
                      <div className="glass-track mb-3 h-1.5 overflow-hidden rounded-full">
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

export default function Dashboard({ monthly = false }) {
  const now = new Date();
  const navigate = useNavigate();
  const { setHeaderActions } = useOutletContext() || {};
  const { categories, setCustomCategories } = useCategories();
  const tab = monthly ? 'monthly' : 'weekly';
  const [screen, setScreen] = useState('setup');
  const [weekInfo, setWeekInfo] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [allowance, setAllowance] = useState(0);
  const [expenses, setExpenses] = useState({});
  const [totals, setTotals] = useState({ fare: 0, food: 0, other: 0, spent: 0, remaining: 0 });
  const [categoryStatus, setCategoryStatus] = useState(null);
  const [categoryLimits, setCategoryLimits] = useState(null);
  const [categoryRules, setCategoryRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [undoItem, setUndoItem] = useState(null);
  const dashboardLoadRef = useRef(null);

  const exportWeeklyCsv = useCallback(() => {
    runExport(() => downloadCsv('/api/export-csv?scope=week'));
  }, []);

  useEffect(() => {
    if (!setHeaderActions) return undefined;
    if (tab === 'weekly' && screen === 'tracker') {
      setHeaderActions(
        <IconButton label="Export weekly CSV" onClick={exportWeeklyCsv}>
          <CsvIcon />
          <span className="hidden sm:inline">Export CSV</span>
        </IconButton>,
      );
    } else {
      setHeaderActions(null);
    }
    return () => setHeaderActions(null);
  }, [tab, screen, setHeaderActions, exportWeeklyCsv]);

  const loadDashboard = useCallback(async () => {
    if (dashboardLoadRef.current) return dashboardLoadRef.current;
    setLoading(true);
    const request = (async () => {
      try {
        const r = await apiFetch('/api/dashboard');
        if (r.status === 401) {
          navigate('/');
          return;
        }
        if (!r.ok) return;
        const d = await r.json();
        applyDashboardData(d, {
          setWeekInfo,
          setAllowance,
          setExpenses,
          setTotals,
          setComparison,
          setScreen,
          setCategoryStatus,
          setCategoryLimits,
          setCategoryRules,
          setCustomCategories,
        });
      } catch { } finally {
        setLoading(false);
        dashboardLoadRef.current = null;
      }
    })();
    dashboardLoadRef.current = request;
    return request;
  }, [navigate, setCustomCategories]);

  const handleBudgetPatch = useCallback((patch) => {
    applyMutationPatch(setExpenses, setTotals, setComparison, patch, {
      setCategoryStatus,
      setCategoryLimits,
      setCategoryRules,
      setCustomCategories,
      categories,
    });
  }, [categories, setCustomCategories]);

  const handleAllowanceChange = useCallback(async (n) => {
    const r = await apiFetch('/api/set-allowance', {
      method: 'POST',
      body: JSON.stringify({ allowance: n }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || 'Failed to update allowance');
    }
    const d = await r.json();
    const patch = patchAllowance(d.allowance, d.totals || totals, expenses, comparison, categories);
    setAllowance(patch.allowance);
    setTotals(patch.totals);
    setComparison(patch.comparison);
  }, [categories, comparison, expenses, totals]);

  const handleItemDeleted = useCallback((item) => {
    setUndoItem(item);
  }, []);

  const dismissUndo = useCallback(() => setUndoItem(null), []);

  const handleUndoDelete = useCallback(async () => {
    if (!undoItem) return;
    const { day, name, amount, category, notes, tags } = undoItem;
    setUndoItem(null);
    try {
      const r = await apiFetch('/api/add-expense-item', {
        method: 'POST',
        body: JSON.stringify({
          day,
          name,
          amount,
          category,
          notes: notes || '',
          tags: tags || [],
        }),
      });
      if (r.ok) handleBudgetPatch(await r.json());
    } catch {
      alert('Could not restore item');
    }
  }, [undoItem, handleBudgetPatch]);

  useEffect(() => {
    primeCsrf();
    loadDashboard();
  }, [loadDashboard]);

  const handleStart = (n) => {
    const emptyTotals = { fare: 0, food: 0, other: 0, spent: 0, remaining: n };
    setAllowance(n);
    setTotals(emptyTotals);
    setComparison((cmp) => patchComparisonFromTotals(cmp, emptyTotals, {}));
    setScreen('tracker');
  };

  return (
    <div className="w-full">
      <UndoToast item={undoItem} onUndo={handleUndoDelete} onDismiss={dismissUndo} />

      {tab === 'weekly' && (
        loading
          ? (
            <div className={`${card} flex min-h-[280px] items-center justify-center p-8`}>
              <p className="text-sm text-purple-soft">Loading your budget…</p>
            </div>
          )
          : screen === 'setup'
            ? <SetupScreen weekInfo={weekInfo} onStart={handleStart} />
            : (
              <WeeklyTracker
                weekInfo={weekInfo}
                allowance={allowance}
                expenses={expenses}
                totals={totals}
                comparison={comparison}
                categoryStatus={categoryStatus}
                categoryRules={categoryRules}
                onBudgetPatch={handleBudgetPatch}
                onAllowanceChange={handleAllowanceChange}
                onItemDeleted={handleItemDeleted}
              />
            )
      )}
      {tab === 'monthly' && (
        <MonthlyTab initMonth={now.getMonth() + 1} initYear={now.getFullYear()} />
      )}
    </div>
  );
}

