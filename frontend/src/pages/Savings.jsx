import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../api';
import SavingsGoals from '../components/SavingsGoals';
import {
  card, cardInner, statLabel, subtext,
} from '../utils/theme';

const PERIODS = [
  { id: 'month', label: 'Month' },
  { id: 'year', label: 'Year' },
  { id: 'all', label: 'All time' },
];

const STATUS_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'closed', label: 'Final' },
  { id: 'in_progress', label: 'In progress' },
];

const RESULT_FILTERS = [
  { id: 'all', label: 'All results' },
  { id: 'under', label: 'Under' },
  { id: 'over', label: 'Over' },
  { id: 'even', label: 'Even' },
];

function money(n) {
  return `₱${Number(n || 0).toFixed(2)}`;
}

function rowResult(row) {
  if (row.status === 'in_progress') {
    if (row.remaining > 0) return 'under';
    if (row.remaining < 0) return 'over';
    return 'even';
  }
  if (row.saved > 0) return 'under';
  if (row.overspent > 0) return 'over';
  return 'even';
}

function FilterChips({ options, value, onChange, ariaLabel }) {
  return (
    <div className="glass-inner flex flex-wrap items-center gap-0.5 rounded-xl p-1" role="group" aria-label={ariaLabel}>
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onChange(opt.id)}
          className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
            value === opt.id
              ? 'bg-purple-primary text-white shadow-glow'
              : 'text-purple-soft hover:bg-purple-primary/15 hover:text-purple-text'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function SummaryTile({ label, value, accent, valueClass, hint }) {
  return (
    <div className={`${cardInner} relative overflow-hidden p-4`}>
      <span className={`absolute inset-x-0 top-0 h-1 ${accent}`} />
      <p className={statLabel}>{label}</p>
      <p className={`mt-1 text-xl font-semibold tracking-tight ${valueClass}`}>
        {money(value)}
      </p>
      {hint ? <p className="mt-0.5 text-[10px] text-purple-muted">{hint}</p> : null}
    </div>
  );
}

function StatusBadge({ status, onTrack }) {
  if (status === 'in_progress') {
    return (
      <span className={`ml-2 inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
        onTrack
          ? 'bg-amber-400/15 text-amber-300'
          : 'bg-red-400/15 text-red-300'
      }`}
      >
        In progress
      </span>
    );
  }
  return (
    <span className="ml-2 inline-flex rounded-md bg-purple-primary/15 px-1.5 py-0.5 text-[10px] font-medium text-purple-primary-light">
      Final
    </span>
  );
}

export default function Savings() {
  const navigate = useNavigate();
  const now = new Date();
  const [period, setPeriod] = useState('year');
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [resultFilter, setResultFilter] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ period });
    if (period === 'month') {
      params.set('month', String(month));
      params.set('year', String(year));
    } else if (period === 'year') {
      params.set('year', String(year));
    }

    try {
      const r = await apiFetch(`/api/savings-snapshot?${params}`);
      if (r.status === 401) {
        navigate('/');
        return;
      }
      const d = await r.json();
      if (!r.ok || d.error) {
        setError(d.error || 'Could not load savings ledger');
        setData(null);
        return;
      }
      setData(d);
    } catch {
      setError('Could not load savings ledger');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [period, month, year, navigate]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setStatusFilter('all');
    setResultFilter('all');
  }, [period, month, year]);

  const shiftMonth = (delta) => {
    let m = month + delta;
    let y = year;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    setMonth(m);
    setYear(y);
  };

  const entries = data?.entries || [];
  const filteredEntries = useMemo(() => (
    entries.filter((row) => {
      if (statusFilter !== 'all' && row.status !== statusFilter) return false;
      if (resultFilter !== 'all' && rowResult(row) !== resultFilter) return false;
      return true;
    })
  ), [entries, statusFilter, resultFilter]);

  const lifetimeSaved = data?.lifetime_saved ?? data?.total_saved ?? 0;
  const netBalance = data?.net_balance ?? data?.running_balance ?? 0;
  const openWeek = data?.open_week;
  const filtersActive = statusFilter !== 'all' || resultFilter !== 'all';

  return (
    <div className="space-y-5">
      <SavingsGoals netBalance={netBalance} />

      <div className={`${card} p-5`}>
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-purple-text">Savings ledger</h2>
            <p className="mt-1 max-w-xl text-xs text-purple-muted">
              Closed weeks credit underspend and debit overspend into your balance.
              The current week stays on track until it ends — leftover never raises next week&apos;s allowance.
            </p>
          </div>
          <div className="glass-inner flex shrink-0 items-center gap-0.5 rounded-xl p-1">
            {PERIODS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPeriod(p.id)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                  period === p.id
                    ? 'bg-purple-primary text-white shadow-glow'
                    : 'text-purple-soft hover:bg-purple-primary/15 hover:text-purple-text'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {period !== 'all' && (
          <div className="mb-5 flex items-center gap-2">
            <div className="glass-inner flex items-center gap-1 rounded-xl p-1">
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text"
                onClick={() => (period === 'month' ? shiftMonth(-1) : setYear((y) => y - 1))}
                aria-label="Previous"
              >
                ←
              </button>
              <span className="min-w-[120px] text-center text-sm font-medium text-purple-text">
                {data?.label || '…'}
              </span>
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-purple-soft transition hover:bg-purple-primary/15 hover:text-purple-text"
                onClick={() => (period === 'month' ? shiftMonth(1) : setYear((y) => y + 1))}
                aria-label="Next"
              >
                →
              </button>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 rounded-full border-2 border-purple-primary/30 border-t-purple-primary login-spinner" />
          </div>
        )}

        {!loading && error && (
          <p className={`py-10 text-center ${subtext}`}>{error}</p>
        )}

        {!loading && !error && data && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <SummaryTile
                label="Lifetime saved"
                value={lifetimeSaved}
                accent="bg-emerald-400"
                valueClass="text-emerald-400"
                hint="Underspend from closed weeks only"
              />
              <SummaryTile
                label="Overspent"
                value={data.total_overspent}
                accent={data.total_overspent > 0 ? 'bg-red-400' : 'bg-purple-primary/40'}
                valueClass={data.total_overspent > 0 ? 'text-red-400' : 'text-purple-muted'}
                hint="Closed weeks over budget"
              />
              <SummaryTile
                label="Net balance"
                value={netBalance}
                accent={netBalance < 0 ? 'bg-red-400' : 'bg-emerald-400'}
                valueClass={netBalance < 0 ? 'text-red-400' : 'text-emerald-400'}
                hint="Lifetime saved − overspent"
              />
              <SummaryTile
                label="Spent (final)"
                value={data.total_spent}
                accent="bg-fuchsia-400"
                valueClass="text-purple-text"
                hint="Closed weeks only"
              />
            </div>

            {openWeek && (
              <div className={`${cardInner} mt-3 p-4`}>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium text-purple-text">
                      This week
                      <StatusBadge status="in_progress" onTrack={openWeek.on_track} />
                    </p>
                    <p className="mt-0.5 text-xs text-purple-muted">{openWeek.label}</p>
                  </div>
                  <p className={`text-sm font-semibold ${openWeek.on_track ? 'text-amber-300' : 'text-red-400'}`}>
                    {openWeek.on_track
                      ? `${money(openWeek.remaining)} remaining`
                      : `${money(Math.abs(openWeek.remaining))} over`}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-purple-muted">Allowance</p>
                    <p className="font-medium text-purple-text-dim">{money(openWeek.allowance)}</p>
                  </div>
                  <div>
                    <p className="text-purple-muted">Spent so far</p>
                    <p className="font-medium text-purple-text">{money(openWeek.spent)}</p>
                  </div>
                  <div>
                    <p className="text-purple-muted">Settles after</p>
                    <p className="font-medium text-purple-soft">{openWeek.week_end}</p>
                  </div>
                </div>
                <p className="mt-3 text-[11px] text-purple-muted">
                  Not added to lifetime saved or net balance until the week closes.
                </p>
              </div>
            )}

            <div className={`${cardInner} mt-3 flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-purple-muted`}>
              <span>
                {data.weeks_closed} closed week{data.weeks_closed === 1 ? '' : 's'}
                {data.weeks_open ? ` · ${data.weeks_open} in progress` : ''}
              </span>
              <span>
                {data.weeks_under} under · {data.weeks_over} over
                {data.weeks_even ? ` · ${data.weeks_even} even` : ''}
              </span>
            </div>
          </>
        )}
      </div>

      {!loading && !error && data && entries.length === 0 && (
        <div className={`${card} py-14 text-center`}>
          <p className={subtext}>No weeks in this period yet</p>
          <p className="mt-2 text-xs text-purple-muted">
            Log expenses on the Weekly tab. Closed weeks settle into this ledger automatically.
          </p>
        </div>
      )}

      {!loading && !error && entries.length > 0 && (
        <div className={`${card} overflow-hidden`}>
          <div className="space-y-3 border-b border-purple-primary/10 px-5 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-purple-text">Week-by-week</h3>
                <p className="mt-0.5 text-xs text-purple-muted">
                  Oldest first · in-progress weeks do not change the running balance
                </p>
              </div>
              {filtersActive && (
                <button
                  type="button"
                  onClick={() => {
                    setStatusFilter('all');
                    setResultFilter('all');
                  }}
                  className="self-start text-xs font-medium text-purple-primary-light transition hover:text-purple-text"
                >
                  Clear filters
                </button>
              )}
            </div>
            <div className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between">
              <FilterChips
                options={STATUS_FILTERS}
                value={statusFilter}
                onChange={setStatusFilter}
                ariaLabel="Filter by week status"
              />
              <FilterChips
                options={RESULT_FILTERS}
                value={resultFilter}
                onChange={setResultFilter}
                ariaLabel="Filter by week result"
              />
            </div>
            <p className="text-xs text-purple-muted">
              Showing {filteredEntries.length} of {entries.length} week{entries.length === 1 ? '' : 's'}
            </p>
          </div>

          {filteredEntries.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className={subtext}>No weeks match these filters</p>
              <button
                type="button"
                onClick={() => {
                  setStatusFilter('all');
                  setResultFilter('all');
                }}
                className="mt-2 text-xs font-medium text-purple-primary-light transition hover:text-purple-text"
              >
                Clear filters
              </button>
            </div>
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-purple-primary/10 text-xs text-purple-muted">
                      <th className="px-5 py-3 font-medium">Week</th>
                      <th className="px-3 py-3 font-medium text-right">Allowance</th>
                      <th className="px-3 py-3 font-medium text-right">Spent</th>
                      <th className="px-3 py-3 font-medium text-right">Saved</th>
                      <th className="px-3 py-3 font-medium text-right">Overspent</th>
                      <th className="px-5 py-3 font-medium text-right">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEntries.map((row) => {
                      const open = row.status === 'in_progress';
                      return (
                        <tr
                          key={row.week_start}
                          className={`border-b border-purple-primary/5 transition hover:bg-purple-primary/5 ${open ? 'bg-amber-400/5' : ''}`}
                        >
                          <td className="px-5 py-3 text-purple-text">
                            {row.label}
                            <StatusBadge status={row.status} onTrack={row.on_track} />
                          </td>
                          <td className="px-3 py-3 text-right text-purple-text-dim">{money(row.allowance)}</td>
                          <td className="px-3 py-3 text-right text-purple-text">{money(row.spent)}</td>
                          <td className="px-3 py-3 text-right text-emerald-400">
                            {open ? '—' : money(row.saved)}
                          </td>
                          <td className={`px-3 py-3 text-right ${!open && row.overspent > 0 ? 'text-red-400' : 'text-purple-muted'}`}>
                            {open ? '—' : money(row.overspent)}
                          </td>
                          <td className={`px-5 py-3 text-right font-semibold ${
                            open
                              ? 'text-purple-muted'
                              : row.running_balance < 0 ? 'text-red-400' : 'text-emerald-400'
                          }`}
                          >
                            {money(row.running_balance)}
                            {open ? (
                              <span className="mt-0.5 block text-[10px] font-normal text-purple-muted">unchanged</span>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="divide-y divide-purple-primary/10 md:hidden">
                {filteredEntries.map((row) => {
                  const open = row.status === 'in_progress';
                  return (
                    <div key={row.week_start} className={`space-y-3 px-5 py-4 ${open ? 'bg-amber-400/5' : ''}`}>
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-purple-text">
                          {row.label}
                          <StatusBadge status={row.status} onTrack={row.on_track} />
                        </p>
                        <p className={`text-sm font-semibold ${
                          row.running_balance < 0 ? 'text-red-400' : 'text-emerald-400'
                        }`}
                        >
                          {money(row.running_balance)}
                        </p>
                      </div>
                      {open ? (
                        <p className="text-xs text-amber-300/90">
                          {row.remaining >= 0
                            ? `${money(row.remaining)} remaining — settles when the week ends`
                            : `${money(Math.abs(row.remaining))} over — settles when the week ends`}
                        </p>
                      ) : null}
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className={`${cardInner} px-3 py-2`}>
                          <p className="text-purple-muted">Allowance</p>
                          <p className="font-medium text-purple-text-dim">{money(row.allowance)}</p>
                        </div>
                        <div className={`${cardInner} px-3 py-2`}>
                          <p className="text-purple-muted">Spent</p>
                          <p className="font-medium text-purple-text">{money(row.spent)}</p>
                        </div>
                        <div className={`${cardInner} px-3 py-2`}>
                          <p className="text-purple-muted">Saved</p>
                          <p className="font-medium text-emerald-400">{open ? '—' : money(row.saved)}</p>
                        </div>
                        <div className={`${cardInner} px-3 py-2`}>
                          <p className="text-purple-muted">Overspent</p>
                          <p className={`font-medium ${!open && row.overspent > 0 ? 'text-red-400' : 'text-purple-muted'}`}>
                            {open ? '—' : money(row.overspent)}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
