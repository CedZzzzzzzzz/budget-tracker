import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch, downloadCsv, openPdf, runExport } from '../api';
import CategoryBadge from '../components/CategoryBadge';
import { useCategories } from '../components/CategoriesContext';
import {
  btnPrimary, card, cardInner, input, label, statLabel, subtext,
} from '../utils/theme';

function money(n) {
  return `₱${Number(n || 0).toFixed(2)}`;
}

function isoDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function defaultRange() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 29);
  return { start: isoDate(start), end: isoDate(end) };
}

function SectionTitle({ children, className = '' }) {
  return (
    <h2 className={`text-sm font-semibold tracking-tight text-purple-text ${className}`}>
      {children}
    </h2>
  );
}

function SummaryTiles({ allowance, spent, saved }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {[
        { label: 'Allowance', value: allowance, text: 'text-purple-primary-light', accent: 'bg-purple-primary' },
        { label: 'Spent', value: spent, text: 'text-purple-text', accent: 'bg-fuchsia-400' },
        {
          label: 'Saved',
          value: saved,
          text: saved < 0 ? 'text-red-400' : 'text-emerald-400',
          accent: saved < 0 ? 'bg-red-400' : 'bg-emerald-400',
        },
      ].map(({ label: l, value, text, accent }) => (
        <div key={l} className={`${cardInner} relative overflow-hidden p-4`}>
          <span className={`absolute inset-x-0 top-0 h-1 ${accent}`} />
          <p className={statLabel}>{l}</p>
          <p className={`mt-1 text-xl font-semibold tracking-tight ${text}`}>{money(value)}</p>
        </div>
      ))}
    </div>
  );
}

function CategoryBreakdown({ breakdown }) {
  const { categories } = useCategories();
  const rows = categories.filter((c) => (breakdown?.[c] || 0) > 0);
  if (!rows.length) {
    return <p className={`py-6 text-center ${subtext}`}>No expenses in this period</p>;
  }
  return (
    <div className="space-y-2">
      {rows.map((c) => (
        <div key={c} className={`${cardInner} flex items-center justify-between px-4 py-3`}>
          <CategoryBadge category={c} />
          <span className="text-sm font-medium text-purple-text">{money(breakdown[c])}</span>
        </div>
      ))}
    </div>
  );
}

function MiniBars({ data }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="flex h-24 items-end gap-1.5">
      {data.map((d) => (
        <div key={d.label} className="flex min-w-0 flex-1 flex-col items-center gap-1">
          <div
            className="w-full max-w-[28px] rounded-t-md bg-gradient-to-t from-purple-primary to-purple-primary-light"
            style={{ height: `${Math.max(4, (d.value / max) * 100)}%` }}
            title={`${d.label}: ${money(d.value)}`}
          />
          <span className="truncate text-[10px] text-purple-muted">{d.short || d.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function Reports() {
  const defaults = useMemo(() => defaultRange(), []);
  const [mode, setMode] = useState('range');
  const [start, setStart] = useState(defaults.start);
  const [end, setEnd] = useState(defaults.end);
  const [year, setYear] = useState(new Date().getFullYear());
  const [rangeData, setRangeData] = useState(null);
  const [yearData, setYearData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadRange = useCallback(async () => {
    if (!start || !end) return;
    setLoading(true);
    setError('');
    try {
      const r = await apiFetch(`/api/report-summary?start=${start}&end=${end}`);
      const data = await r.json();
      if (!r.ok) {
        setError(data.error || 'Could not load report');
        setRangeData(null);
        return;
      }
      setRangeData(data);
    } catch {
      setError('Could not load report');
      setRangeData(null);
    } finally {
      setLoading(false);
    }
  }, [start, end]);

  const loadYear = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const r = await apiFetch(`/api/yearly-summary?year=${year}`);
      const data = await r.json();
      if (!r.ok) {
        setError(data.error || 'Could not load yearly summary');
        setYearData(null);
        return;
      }
      setYearData(data);
    } catch {
      setError('Could not load yearly summary');
      setYearData(null);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    if (mode === 'range') loadRange();
    else loadYear();
  }, [mode, loadRange, loadYear]);

  const active = mode === 'range' ? rangeData : yearData;
  const empty = mode === 'range'
    ? !rangeData || rangeData.num_weeks === 0
    : !yearData || yearData.num_months === 0;

  return (
    <div className="space-y-5">
      <div className={`${card} p-5`}>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <SectionTitle>Reports</SectionTitle>
            <p className={`mt-1 ${subtext}`}>
              Custom date ranges and a full-year rollup with CSV / PDF export.
            </p>
          </div>
          <div className="glass-inner flex shrink-0 items-center gap-0.5 rounded-xl p-1">
            {[
              { id: 'range', label: 'Date range' },
              { id: 'year', label: 'Yearly' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setMode(tab.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  mode === tab.id
                    ? 'bg-purple-primary text-white shadow-glow'
                    : 'text-purple-soft hover:bg-purple-primary/15 hover:text-purple-text'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {mode === 'range' ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <div>
              <label className={label} htmlFor="report-start">From</label>
              <input
                id="report-start"
                type="date"
                className={input}
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div>
              <label className={label} htmlFor="report-end">To</label>
              <input
                id="report-end"
                type="date"
                className={input}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <div className="flex items-end">
              <button type="button" className={`${btnPrimary} w-full sm:w-auto`} onClick={loadRange} disabled={loading}>
                {loading ? 'Loading…' : 'Run report'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className={label} htmlFor="report-year">Year</label>
              <input
                id="report-year"
                type="number"
                min="2000"
                max="2100"
                className={`${input} w-32`}
                value={year}
                onChange={(e) => setYear(Number(e.target.value) || new Date().getFullYear())}
              />
            </div>
            <button type="button" className={btnPrimary} onClick={loadYear} disabled={loading}>
              {loading ? 'Loading…' : 'Load year'}
            </button>
            <div className="glass-inner flex items-center gap-1 rounded-xl p-1">
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text"
                onClick={() => setYear((y) => y - 1)}
                aria-label="Previous year"
              >
                ←
              </button>
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text"
                onClick={() => setYear((y) => y + 1)}
                aria-label="Next year"
              >
                →
              </button>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && !active && (
        <div className="flex justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-purple-primary/30 border-t-purple-primary login-spinner" />
        </div>
      )}

      {!loading && !error && empty && (
        <div className={`${card} py-14 text-center`}>
          <p className={subtext}>No budget data for this period</p>
          <p className="mt-2 text-xs text-purple-muted">Log weekly expenses first, then come back here.</p>
        </div>
      )}

      {!empty && active && (
        <div className={`${card} space-y-5 p-5`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <SectionTitle>{active.label}</SectionTitle>
              <p className="mt-1 text-xs text-purple-muted">
                {mode === 'range'
                  ? `${active.num_weeks} week${active.num_weeks === 1 ? '' : 's'} in range`
                  : `${active.num_months} month${active.num_months === 1 ? '' : 's'} · ${active.num_weeks} week${active.num_weeks === 1 ? '' : 's'}`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="glass-btn-ghost rounded-xl px-3 py-2 text-xs font-medium text-purple-soft hover:text-purple-text"
                onClick={() => runExport(() => (
                  mode === 'range'
                    ? downloadCsv(`/api/export-csv?scope=range&start=${start}&end=${end}`)
                    : downloadCsv(`/api/export-csv?scope=year&year=${year}`)
                ))}
              >
                Export CSV
              </button>
              <button
                type="button"
                className={`${btnPrimary} !px-3 !py-2 !text-xs`}
                onClick={() => runExport(() => (
                  mode === 'range'
                    ? openPdf(`/api/export-range-pdf?start=${start}&end=${end}`)
                    : openPdf(`/api/export-yearly-pdf?year=${year}`)
                ))}
              >
                Export PDF
              </button>
            </div>
          </div>

          <SummaryTiles
            allowance={active.total_allowance}
            spent={active.total_spent}
            saved={active.total_saved}
          />

          <div className={mode === 'year' ? 'grid grid-cols-1 gap-5 lg:grid-cols-2' : ''}>
            <div>
              <SectionTitle className="mb-3">By category</SectionTitle>
              <CategoryBreakdown breakdown={active.breakdown} />
            </div>
            {mode === 'year' && (
              <div className={`${cardInner} p-4`}>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-medium text-purple-text">Spending by month</p>
                  <span className="text-xs text-purple-muted">{money(active.total_spent)} total</span>
                </div>
                <MiniBars
                  data={(active.months || []).map((m) => ({
                    label: m.month_name,
                    short: m.label,
                    value: m.spent,
                  }))}
                />
              </div>
            )}
          </div>

          {mode === 'range' && active.weeks?.length > 0 && (
            <div>
              <SectionTitle className="mb-3">Weeks in range</SectionTitle>
              <div className="space-y-2">
                {active.weeks.map((w) => (
                  <div key={w.week_start} className={`${cardInner} grid grid-cols-2 gap-2 px-4 py-3 sm:grid-cols-4`}>
                    <div>
                      <p className={statLabel}>Week</p>
                      <p className="text-sm text-purple-text">{w.week_start}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Allowance</p>
                      <p className="text-sm text-purple-primary-light">{money(w.allowance)}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Spent</p>
                      <p className="text-sm text-purple-text">{money(w.spent)}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Saved</p>
                      <p className={`text-sm ${w.saved < 0 ? 'text-red-400' : 'text-emerald-400'}`}>{money(w.saved)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {mode === 'year' && active.months?.length > 0 && (
            <div>
              <SectionTitle className="mb-3">Months</SectionTitle>
              <div className="space-y-2">
                {active.months.map((m) => (
                  <div key={m.month} className={`${cardInner} grid grid-cols-2 gap-2 px-4 py-3 sm:grid-cols-5`}>
                    <div>
                      <p className={statLabel}>Month</p>
                      <p className="text-sm text-purple-text">{m.month_name}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Weeks</p>
                      <p className="text-sm text-purple-soft">{m.num_weeks}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Allowance</p>
                      <p className="text-sm text-purple-primary-light">{money(m.allowance)}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Spent</p>
                      <p className="text-sm text-purple-text">{money(m.spent)}</p>
                    </div>
                    <div>
                      <p className={statLabel}>Saved</p>
                      <p className={`text-sm ${m.saved < 0 ? 'text-red-400' : 'text-emerald-400'}`}>{money(m.saved)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
