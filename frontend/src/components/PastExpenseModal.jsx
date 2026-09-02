import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { apiFetch, parseApiResponse } from '../api';
import { input, label, btnPrimary, btnGhost, heading, subtext } from '../utils/theme';

export default function PastExpenseModal({ isOpen, onClose, onExpenseAdded, categories = [] }) {
  const getTodayStr = () => new Date().toISOString().split('T')[0];
  const getPastSevenDaysStr = () => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split('T')[0];
  };

  const fileInputRef = useRef(null);
  const [itemDate, setItemDate] = useState(getPastSevenDaysStr());
  const [name, setName] = useState('');
  const [cost, setCost] = useState('');
  const [category, setCategory] = useState(categories[0]?.id || 'Food');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleScanReceipt = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanning(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('receipt', file);
      const res = await apiFetch('/api/receipt-scans/extract', {
        method: 'POST',
        body: formData,
      });
      const { data, ok } = await parseApiResponse(res);
      if (!ok) {
        setError(data.error || 'Could not scan receipt');
        return;
      }

      const r = data.receipt || {};
      if (r.transaction_date && r.transaction_date <= getTodayStr()) {
        setItemDate(r.transaction_date);
      }
      if (r.merchant || data.items?.[0]?.name) {
        setName(r.merchant || data.items[0].name);
      }
      if (r.total || data.items?.[0]?.amount) {
        setCost(String(r.total || data.items[0].amount));
      }
      if (data.items?.[0]?.category) {
        setCategory(data.items[0].category);
      }
    } catch {
      setError('Failed to extract receipt data.');
    } finally {
      setScanning(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const parsedCost = parseFloat(cost);
    if (!name.trim()) {
      setError('Please enter a description for the expense.');
      return;
    }
    if (isNaN(parsedCost) || parsedCost <= 0) {
      setError('Please enter a valid amount.');
      return;
    }
    if (!itemDate) {
      setError('Please select a date.');
      return;
    }

    setSaving(true);
    try {
      const res = await apiFetch('/api/add-expense-item', {
        method: 'POST',
        body: JSON.stringify({
          item_date: itemDate,
          name: name.trim(),
          cost: parsedCost,
          category: category,
          notes: notes.trim(),
        }),
      });

      const { data, ok } = await parseApiResponse(res);
      if (!ok) {
        setError(data.error || 'Failed to log past expense');
        return;
      }

      onExpenseAdded?.(data);
      onClose();
      setName('');
      setCost('');
      setNotes('');
    } catch {
      setError('An error occurred while saving past expense.');
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md animate-fadeIn">
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-purple-border/35 bg-gradient-to-b from-[#250b4d]/95 via-[#190636]/95 to-[#110328]/98 p-6 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.85),0_0_40px_rgba(139,60,224,0.2)] backdrop-blur-2xl light:bg-white light:border-purple-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="past-expense-title"
      >
        <div className="relative flex items-start justify-between border-b border-purple-border/20 pb-4 mb-4 pr-10">
          <div>
            <h2 id="past-expense-title" className="text-xl font-bold tracking-tight text-purple-text">
              Log Past Week Expense
            </h2>
            <p className="mt-1 text-xs text-purple-soft">
              Did you forget to log something from last week or a past date? Record it here.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="absolute top-0 right-0 flex h-8 w-8 items-center justify-center rounded-xl bg-white/5 text-purple-muted hover:bg-purple-primary/20 hover:text-purple-text transition"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <div className="mb-5 flex items-center justify-between rounded-2xl border border-purple-primary/25 bg-purple-primary/10 p-3">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-purple-primary/20 text-purple-primary-light">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 7h3l1.5-2h5L16 7h3a2 2 0 0 1 2 2v9H3V9a2 2 0 0 1 2-2Z" />
                <circle cx="12" cy="12.5" r="3.5" />
              </svg>
            </span>
            <div>
              <p className="text-xs font-semibold text-purple-text">Have a physical receipt?</p>
              <p className="text-[11px] text-purple-soft">Auto-fill date, description, amount & category</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 rounded-xl bg-purple-primary/25 px-3 py-1.5 text-xs font-semibold text-purple-primary-light hover:bg-purple-primary hover:text-white transition disabled:opacity-50 whitespace-nowrap ml-2"
            title="Scan a receipt image to auto-fill expense details"
          >
            {scanning ? 'Scanning...' : 'Scan Receipt'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleScanReceipt}
          />
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300 light:text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={label}>Expense Date</label>
            <input
              type="date"
              max={getTodayStr()}
              value={itemDate}
              onChange={(e) => setItemDate(e.target.value)}
              className="glass-input w-full rounded-xl border border-purple-border/30 bg-white/[0.06] px-4 py-3 text-sm text-purple-text placeholder:text-purple-muted/60 focus:border-purple-primary-light/60 focus:bg-white/[0.09] focus:outline-none focus:ring-2 focus:ring-purple-primary/40 transition"
              required
            />
          </div>

          <div>
            <label className={label}>Expense Description</label>
            <input
              type="text"
              placeholder="e.g. Groceries, Bus fare, Coffee"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="glass-input w-full rounded-xl border border-purple-border/30 bg-white/[0.06] px-4 py-3 text-sm text-purple-text placeholder:text-purple-muted/60 focus:border-purple-primary-light/60 focus:bg-white/[0.09] focus:outline-none focus:ring-2 focus:ring-purple-primary/40 transition"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={label}>Amount</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                placeholder="0.00"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                className="glass-input w-full rounded-xl border border-purple-border/30 bg-white/[0.06] px-4 py-3 text-sm text-purple-text placeholder:text-purple-muted/60 focus:border-purple-primary-light/60 focus:bg-white/[0.09] focus:outline-none focus:ring-2 focus:ring-purple-primary/40 transition"
                required
              />
            </div>

            <div>
              <label className={label}>Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="glass-input w-full rounded-xl border border-purple-border/30 bg-[#1c083c] px-4 py-3 text-sm text-purple-text focus:border-purple-primary-light/60 focus:outline-none focus:ring-2 focus:ring-purple-primary/40 transition"
              >
                {categories.map((cat) => (
                  <option key={cat.id || cat.name} value={cat.id || cat.name} className="bg-[#1c083c] text-purple-text">
                    {cat.name || cat.id}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className={label}>Notes (Optional)</label>
            <input
              type="text"
              placeholder="Add extra details..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="glass-input w-full rounded-xl border border-purple-border/30 bg-white/[0.06] px-4 py-3 text-sm text-purple-text placeholder:text-purple-muted/60 focus:border-purple-primary-light/60 focus:bg-white/[0.09] focus:outline-none focus:ring-2 focus:ring-purple-primary/40 transition"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-5 border-t border-purple-border/20">
            <button
              type="button"
              onClick={onClose}
              className="glass-btn-ghost rounded-xl px-5 py-3 text-sm font-medium text-purple-text-dim hover:bg-white/10 hover:text-purple-text transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#5a189a] via-[#7b2cbf] to-[#9d4edd] px-6 py-3 text-sm font-semibold text-white border border-purple-primary/30 shadow-[0_4px_20px_rgba(123,44,191,0.4)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Add Past Expense'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
