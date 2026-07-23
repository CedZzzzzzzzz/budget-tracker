import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiFetch, parseApiResponse } from '../api';
import {
  adminGlassControl,
  adminGlassInset,
  adminGlassPanel,
} from '../utils/adminGlass';
import { btnPrimary, label, subtext } from '../utils/theme';


const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];


function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 7h3l1.5-2h5L16 7h3a2 2 0 0 1 2 2v9H3V9a2 2 0 0 1 2-2Z" />
      <circle cx="12" cy="12.5" r="3.5" />
    </svg>
  );
}


function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}


function dayFromReceiptDate(receiptDate, weekInfo, fallback) {
  if (!receiptDate || !weekInfo?.week_start || !weekInfo?.week_end) return fallback;
  if (receiptDate < weekInfo.week_start || receiptDate > weekInfo.week_end) return fallback;
  const parsed = new Date(`${receiptDate}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? fallback : DAY_NAMES[parsed.getDay()];
}


function receiptDateOutsideWeek(receiptDate, weekInfo) {
  if (!receiptDate || !weekInfo?.week_start || !weekInfo?.week_end) return false;
  return receiptDate < weekInfo.week_start || receiptDate > weekInfo.week_end;
}


function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}


function formatReceiptAmount(value, currency = 'PHP') {
  const amount = Number(value || 0);
  const currencyCode = /^[A-Z]{3}$/.test(currency) ? currency : 'PHP';
  try {
    return new Intl.NumberFormat('en-PH', {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currencyCode} ${amount.toFixed(2)}`;
  }
}


export default function ReceiptScanner({
  open,
  onClose,
  onSaved,
  defaultDay,
  weekInfo,
  categoryLabels,
}) {
  const dialogRef = useRef(null);
  const fileInputRef = useRef(null);
  const fileButtonRef = useRef(null);
  const abortRef = useRef(null);
  const returnFocusRef = useRef(null);
  const idempotencyKeyRef = useRef(createIdempotencyKey());
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState(null);
  const [mode, setMode] = useState('total');
  const [itemizedItems, setItemizedItems] = useState([]);
  const [totalItem, setTotalItem] = useState(null);
  const [day, setDay] = useState(defaultDay || DAY_NAMES[new Date().getDay()]);
  const [categoryOptions, setCategoryOptions] = useState([]);

  const clearPreview = useCallback(() => {
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return '';
    });
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    clearPreview();
    setFile(null);
    setProcessing(false);
    setSaving(false);
    setError('');
    setDraft(null);
    setMode('total');
    setItemizedItems([]);
    setTotalItem(null);
    setDay(defaultDay || DAY_NAMES[new Date().getDay()]);
    setCategoryOptions([]);
    idempotencyKeyRef.current = createIdempotencyKey();
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [clearPreview, defaultDay]);

  const close = useCallback(() => {
    const returnTarget = returnFocusRef.current;
    reset();
    onClose();
    requestAnimationFrame(() => returnTarget?.focus());
  }, [onClose, reset]);

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement;
    requestAnimationFrame(() => fileButtonRef.current?.focus());
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !processing && !saving) close();
      if (event.key === 'Tab') {
        const controls = dialogRef.current?.querySelectorAll(
          'button:not([disabled]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled])',
        );
        if (!controls?.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
    };
  }, [close, open, processing, saving]);

  useEffect(() => () => {
    abortRef.current?.abort();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const selectedItems = useMemo(
    () => (mode === 'itemized' ? itemizedItems : totalItem ? [totalItem] : []),
    [itemizedItems, mode, totalItem],
  );

  const selectedTotal = useMemo(
    () => selectedItems.reduce((sum, item) => sum + Number(item.amount || 0), 0),
    [selectedItems],
  );

  const chooseFile = (event) => {
    const nextFile = event.target.files?.[0];
    if (!nextFile) return;
    clearPreview();
    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
    setDraft(null);
    setItemizedItems([]);
    setTotalItem(null);
    setError('');
    idempotencyKeyRef.current = createIdempotencyKey();
  };

  const removeFile = () => {
    clearPreview();
    setFile(null);
    setError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    fileButtonRef.current?.focus();
  };

  const scan = async () => {
    if (!file || processing) return;
    setProcessing(true);
    setError('');
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const body = new FormData();
      body.append('receipt', file);
      const response = await apiFetch('/api/receipt-scans/extract', {
        method: 'POST',
        body,
        signal: controller.signal,
      });
      const { data, ok } = await parseApiResponse(response);
      if (!ok) {
        setError(data.error || 'The receipt could not be scanned.');
        return;
      }
      const items = (data.items || []).map((item, index) => ({
        client_id: `${index}-${item.name}`,
        name: item.name || '',
        amount: String(item.amount ?? ''),
        category: item.category || 'other',
        needs_review: Boolean(item.needs_review),
      }));
      const firstCategory = items[0]?.category || 'other';
      const merchant = data.receipt?.merchant || 'Receipt purchase';
      const total = Number(data.receipt?.total || 0);
      const warnings = [...(data.warnings || [])];
      if (receiptDateOutsideWeek(data.receipt?.purchase_date, weekInfo)) {
        warnings.push('The receipt date is outside the current week. Choose the day to use.');
      }
      setDraft({ ...data, warnings });
      setCategoryOptions(data.categories || []);
      setItemizedItems(items);
      setTotalItem({
        client_id: 'receipt-total',
        name: merchant,
        amount: total > 0 ? String(total) : '',
        category: firstCategory,
        needs_review: items.some((item) => item.needs_review),
      });
      setMode(data.mode === 'itemized' ? 'itemized' : 'total');
      setDay(dayFromReceiptDate(data.receipt?.purchase_date, weekInfo, defaultDay));
      clearPreview();
      setFile(null);
    } catch (scanError) {
      if (scanError?.name !== 'AbortError') {
        setError('The receipt scan was interrupted. Please try again.');
      }
    } finally {
      abortRef.current = null;
      setProcessing(false);
    }
  };

  const updateItem = (clientId, field, value) => {
    const update = (item) => (
      item.client_id === clientId
        ? { ...item, [field]: value, needs_review: false }
        : item
    );
    if (mode === 'itemized') {
      setItemizedItems((current) => current.map(update));
    } else {
      setTotalItem((current) => current ? update(current) : current);
    }
  };

  const removeItem = (clientId) => {
    setItemizedItems((current) => current.filter((item) => item.client_id !== clientId));
  };

  const save = async () => {
    if (saving || selectedItems.length === 0) return;
    const merchant = String(draft?.receipt?.merchant || '').trim();
    const items = selectedItems.map((item) => ({
      name: item.name.trim(),
      amount: Number(item.amount),
      category: item.category,
      notes: mode === 'itemized' && merchant ? `Merchant: ${merchant}` : '',
      tags: [],
    }));
    if (items.some((item) => !item.name || !Number.isFinite(item.amount) || item.amount <= 0)) {
      setError('Review every item name and amount before saving.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const response = await apiFetch('/api/expense-items/batch', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKeyRef.current },
        body: JSON.stringify({ day, items }),
      });
      const { data, ok } = await parseApiResponse(response);
      if (!ok) {
        setError(data.error || 'The receipt items could not be saved.');
        return;
      }
      onSaved(data);
      close();
    } catch {
      setError('The receipt items could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[2200] flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-5"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="receipt-scanner-title"
        className={`${adminGlassPanel} flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden !rounded-b-none !rounded-t-3xl !bg-[linear-gradient(145deg,#170632_0%,#150624_46%,#0f061b_100%)] sm:!rounded-3xl`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.07] bg-transparent px-5 py-4 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-purple-muted">Expense capture</p>
            <h2 id="receipt-scanner-title" className="mt-1 text-xl font-semibold text-purple-text">Scan a receipt</h2>
            <p className={`mt-1 ${subtext}`}>Review every extracted value before it is added.</p>
          </div>
          <button
            type="button"
            onClick={close}
            disabled={processing || saving}
            aria-label="Close receipt scanner"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/10 text-purple-soft transition hover:border-purple-primary/35 hover:bg-purple-primary/10 hover:text-purple-text disabled:opacity-40"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          <div className="sr-only" aria-live="polite">
            {processing
              ? 'Reading receipt.'
              : saving
                ? 'Adding expenses.'
                : draft
                  ? 'Receipt ready for review.'
                  : ''}
          </div>
          {error && (
            <div role="alert" className={`${adminGlassInset} mb-4 !border-red-400/25 !bg-red-500/10 px-4 py-3 text-sm text-red-200`}>
              {error}
            </div>
          )}

          {!draft && (
            <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(240px,.7fr)]">
              <div className={`${adminGlassInset} relative flex min-h-64 items-center justify-center overflow-hidden !rounded-2xl border-dashed !border-purple-primary/30`}>
                {previewUrl ? (
                  <>
                    <img src={previewUrl} alt="Selected receipt preview" className="max-h-[420px] w-full object-contain" />
                    <button
                      type="button"
                      onClick={removeFile}
                      className="absolute right-3 top-3 min-h-11 rounded-xl border border-white/15 bg-black/70 px-4 text-xs font-semibold text-white backdrop-blur-sm"
                    >
                      Remove photo
                    </button>
                  </>
                ) : (
                  <div className="px-6 text-center">
                    <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-purple-primary/15 text-purple-primary-light"><CameraIcon /></span>
                    <p className="mt-4 text-sm font-medium text-purple-text">Choose a clear receipt photo</p>
                    <p className="mt-1 text-xs leading-5 text-purple-muted">JPEG, PNG, or WebP. Keep the total and item lines visible.</p>
                  </div>
                )}
              </div>
              <div className={`${adminGlassInset} flex flex-col justify-center p-4 sm:p-5`}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  capture="environment"
                  onChange={chooseFile}
                  className="sr-only"
                  tabIndex={-1}
                />
                <div className={`${adminGlassControl} flex h-auto min-h-14 items-center gap-3 p-2`}>
                  <button
                    ref={fileButtonRef}
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={processing}
                    className="min-h-10 shrink-0 rounded-lg bg-purple-primary/25 px-4 text-sm font-semibold text-purple-primary-light transition hover:bg-purple-primary/35 disabled:opacity-40"
                  >
                    Choose receipt
                  </button>
                  <span className="min-w-0 truncate text-sm text-purple-soft" aria-live="polite">
                    {file?.name || 'No file selected'}
                  </span>
                </div>
                <p className="mt-4 text-xs leading-5 text-purple-muted">
                  The image is sent to the configured OCR provider for this scan and is not stored by Budget Tracker.
                </p>
                <button type="button" onClick={scan} disabled={!file || processing} className={`${btnPrimary} mt-5 w-full`}>
                  {processing ? 'Reading receipt…' : 'Extract receipt'}
                </button>
              </div>
            </div>
          )}

          {draft && (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className={`${adminGlassInset} p-3`}>
                  <p className="text-[11px] uppercase tracking-[0.12em] text-purple-muted">Merchant</p>
                  <p className="mt-1 truncate text-sm font-medium text-purple-text">{draft.receipt?.merchant || 'Unknown'}</p>
                </div>
                <div className={`${adminGlassInset} p-3`}>
                  <p className="text-[11px] uppercase tracking-[0.12em] text-purple-muted">Receipt total</p>
                  <p className="mt-1 text-sm font-medium text-purple-text">
                    {formatReceiptAmount(draft.receipt?.total, draft.receipt?.currency)}
                  </p>
                </div>
                <label className={`${adminGlassInset} p-3`}>
                  <span className="text-[11px] uppercase tracking-[0.12em] text-purple-muted">Add to day</span>
                  <select value={day} onChange={(event) => setDay(event.target.value)} className={`${adminGlassControl} mt-2 !min-h-9 !px-2.5 !py-1.5 font-medium`}>
                    {DAY_NAMES.map((dayName) => <option key={dayName} value={dayName}>{dayName}</option>)}
                  </select>
                </label>
              </div>

              {(draft.warnings || []).length > 0 && (
                <div className={`${adminGlassInset} !border-amber-400/20 !bg-amber-500/10 px-4 py-3`}>
                  <p className="text-xs font-semibold text-amber-200">Review needed</p>
                  <ul className="mt-1 space-y-1 text-xs text-amber-100/80">
                    {draft.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
                  </ul>
                </div>
              )}

              <div className={`${adminGlassInset} grid grid-cols-2 gap-2 p-1`}>
                <button type="button" onClick={() => setMode('total')} className={`min-h-10 rounded-lg px-3 text-sm font-medium transition ${mode === 'total' ? 'bg-purple-primary text-white' : 'text-purple-soft hover:bg-white/5'}`}>Use total only</button>
                <button type="button" onClick={() => setMode('itemized')} disabled={itemizedItems.length === 0} className={`min-h-10 rounded-lg px-3 text-sm font-medium transition disabled:opacity-35 ${mode === 'itemized' ? 'bg-purple-primary text-white' : 'text-purple-soft hover:bg-white/5'}`}>Use itemized list</button>
              </div>

              <div className="space-y-3">
                {selectedItems.map((item, index) => (
                  <div key={item.client_id} className={`${adminGlassInset} !rounded-2xl p-4`}>
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="min-w-0 text-xs font-semibold uppercase tracking-[0.12em] text-purple-muted">
                        Item {index + 1}
                        {mode === 'itemized' && draft.receipt?.merchant && (
                          <span className="ml-2 normal-case tracking-normal text-purple-soft">
                            from {draft.receipt.merchant}
                          </span>
                        )}
                      </p>
                      <div className="flex items-center gap-2">
                        {item.needs_review && <span className="rounded-md bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-200">Review</span>}
                        {mode === 'itemized' && itemizedItems.length > 1 && (
                          <button type="button" onClick={() => removeItem(item.client_id)} className="text-xs font-medium text-red-300">Remove</button>
                        )}
                      </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-[minmax(0,1.4fr)_120px_minmax(150px,.8fr)]">
                      <label>
                        <span className={label}>Name</span>
                        <input value={item.name} onChange={(event) => updateItem(item.client_id, 'name', event.target.value)} className={adminGlassControl} maxLength={200} />
                      </label>
                      <label>
                        <span className={label}>Amount</span>
                        <input type="number" value={item.amount} onChange={(event) => updateItem(item.client_id, 'amount', event.target.value)} className={adminGlassControl} min="0.01" step="0.01" />
                      </label>
                      <label>
                        <span className={label}>Category</span>
                        <select value={item.category} onChange={(event) => updateItem(item.client_id, 'category', event.target.value)} className={adminGlassControl}>
                          {categoryOptions.map((category) => (
                            <option key={category.slug} value={category.slug}>
                              {category.label || categoryLabels?.[category.slug] || category.slug}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </div>
                ))}
              </div>

              <div className={`${adminGlassInset} flex items-center justify-between px-4 py-3`}>
                <span className="text-sm text-purple-muted">Amount to add</span>
                <span className="text-lg font-semibold text-purple-primary-light">
                  {formatReceiptAmount(selectedTotal, draft.receipt?.currency)}
                </span>
              </div>
            </div>
          )}
        </div>

        {draft && (
          <div className="grid grid-cols-2 gap-3 border-t border-white/10 bg-white/[0.025] px-5 py-4 backdrop-blur-xl sm:flex sm:justify-end sm:px-6">
            <button type="button" onClick={close} disabled={saving} className={`${adminGlassInset} min-h-11 px-5 text-sm font-semibold text-purple-soft transition hover:border-purple-primary/35 hover:text-purple-text disabled:opacity-40`}>Cancel</button>
            <button type="button" onClick={save} disabled={saving || selectedItems.length === 0} className={`${btnPrimary} min-h-11 px-5`}>
              {saving ? 'Adding…' : `Add ${selectedItems.length} ${selectedItems.length === 1 ? 'expense' : 'expenses'}`}
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
