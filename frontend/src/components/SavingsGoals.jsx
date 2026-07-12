import { useCallback, useEffect, useState } from 'react';
import { apiFetch, parseApiResponse } from '../api';
import {
  card, cardInner, input, label, btnPrimary, subtext, statLabel,
} from '../utils/theme';

function money(n) {
  return `₱${Number(n || 0).toFixed(2)}`;
}

function ProgressBar({ pct, complete }) {
  return (
    <div className="glass-track h-2 overflow-hidden rounded-full">
      <div
        className={`h-full rounded-full transition-all duration-700 ${
          complete ? 'bg-emerald-400' : 'bg-purple-primary'
        }`}
        style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
      />
    </div>
  );
}

const emptyForm = {
  name: '',
  target_amount: '',
  current_amount: '',
  deadline: '',
};

export default function SavingsGoals({ netBalance = 0 }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [contributeId, setContributeId] = useState(null);
  const [contributeAmount, setContributeAmount] = useState('');
  const [formOpen, setFormOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const r = await apiFetch('/api/savings-goals');
      const { data, ok } = await parseApiResponse(r);
      if (!ok) {
        setError(data.error || 'Could not load goals');
        return;
      }
      setGoals(data.goals || []);
    } catch {
      setError('Could not load goals');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
    setFormOpen(false);
  };

  const startEdit = (goal) => {
    setEditingId(goal.id);
    setForm({
      name: goal.name,
      target_amount: String(goal.target_amount),
      current_amount: String(goal.current_amount),
      deadline: goal.deadline || '',
    });
    setFormOpen(true);
    setContributeId(null);
  };

  const submitGoal = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    const body = {
      name: form.name.trim(),
      target_amount: Number(form.target_amount),
      current_amount: form.current_amount === '' ? 0 : Number(form.current_amount),
      deadline: form.deadline || null,
    };
    try {
      const path = editingId ? `/api/savings-goals/${editingId}` : '/api/savings-goals';
      const r = await apiFetch(path, {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(body),
      });
      const { data, ok } = await parseApiResponse(r);
      if (!ok) {
        setError(data.error || 'Could not save goal');
        return;
      }
      setGoals(data.goals || []);
      resetForm();
    } catch {
      setError('Could not save goal');
    } finally {
      setSaving(false);
    }
  };

  const submitContribute = async (e) => {
    e.preventDefault();
    if (!contributeId) return;
    setSaving(true);
    setError('');
    try {
      const r = await apiFetch(`/api/savings-goals/${contributeId}/contribute`, {
        method: 'POST',
        body: JSON.stringify({ amount: Number(contributeAmount) }),
      });
      const { data, ok } = await parseApiResponse(r);
      if (!ok) {
        setError(data.error || 'Could not add contribution');
        return;
      }
      setGoals(data.goals || []);
      setContributeId(null);
      setContributeAmount('');
    } catch {
      setError('Could not add contribution');
    } finally {
      setSaving(false);
    }
  };

  const removeGoal = async (goal) => {
    if (!confirm(`Delete goal “${goal.name}”?`)) return;
    try {
      const r = await apiFetch(`/api/savings-goals/${goal.id}`, { method: 'DELETE' });
      const { data, ok } = await parseApiResponse(r);
      if (!ok) {
        setError(data.error || 'Could not delete goal');
        return;
      }
      setGoals(data.goals || []);
    } catch {
      setError('Could not delete goal');
    }
  };

  const archiveGoal = async (goal) => {
    try {
      const r = await apiFetch(`/api/savings-goals/${goal.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'archived' }),
      });
      const { data, ok } = await parseApiResponse(r);
      if (!ok) {
        setError(data.error || 'Could not archive goal');
        return;
      }
      setGoals(data.goals || []);
    } catch {
      setError('Could not archive goal');
    }
  };

  return (
    <div className={`${card} p-5`}>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-purple-text">Savings goals</h2>
          <p className="mt-1 max-w-xl text-xs text-purple-muted">
            Set a target and track progress. Contributions are manual — they don&apos;t change your weekly allowance.
            {netBalance > 0 ? (
              <span className="text-purple-soft">
                {' '}Net ledger balance available as a guide: {money(netBalance)}.
              </span>
            ) : null}
          </p>
        </div>
        <button
          type="button"
          className={`${btnPrimary} shrink-0 !px-3 !py-2 !text-xs`}
          onClick={() => {
            resetForm();
            setFormOpen(true);
          }}
        >
          New goal
        </button>
      </div>

      {error && (
        <p className="mb-3 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {formOpen && (
        <form onSubmit={submitGoal} className={`${cardInner} mb-4 space-y-3 p-4`}>
          <p className="text-sm font-medium text-purple-text">
            {editingId ? 'Edit goal' : 'Create goal'}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={label} htmlFor="goal-name">Name</label>
              <input
                id="goal-name"
                className={input}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Emergency fund"
                required
                maxLength={200}
              />
            </div>
            <div>
              <label className={label} htmlFor="goal-target">Target</label>
              <input
                id="goal-target"
                className={input}
                type="number"
                min="0.01"
                step="0.01"
                value={form.target_amount}
                onChange={(e) => setForm((f) => ({ ...f, target_amount: e.target.value }))}
                placeholder="10000"
                required
              />
            </div>
            <div>
              <label className={label} htmlFor="goal-current">Saved so far</label>
              <input
                id="goal-current"
                className={input}
                type="number"
                min="0"
                step="0.01"
                value={form.current_amount}
                onChange={(e) => setForm((f) => ({ ...f, current_amount: e.target.value }))}
                placeholder="0"
              />
            </div>
            <div className="sm:col-span-2">
              <label className={label} htmlFor="goal-deadline">Deadline (optional)</label>
              <input
                id="goal-deadline"
                className={input}
                type="date"
                value={form.deadline}
                onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={`${btnPrimary} !px-3 !py-2 !text-xs`} disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Update goal' : 'Add goal'}
            </button>
            <button
              type="button"
              className="rounded-xl px-3 py-2 text-xs font-medium text-purple-soft transition hover:bg-purple-primary/10 hover:text-purple-text"
              onClick={resetForm}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading && (
        <div className="flex justify-center py-10">
          <div className="h-7 w-7 rounded-full border-2 border-purple-primary/30 border-t-purple-primary login-spinner" />
        </div>
      )}

      {!loading && goals.length === 0 && (
        <div className="py-10 text-center">
          <p className={subtext}>No savings goals yet</p>
          <p className="mt-1 text-xs text-purple-muted">
            Create a goal like “Laptop” or “Emergency fund” and add progress as you save.
          </p>
        </div>
      )}

      {!loading && goals.length > 0 && (
        <div className="space-y-3">
          {goals.map((goal) => (
            <div key={goal.id} className={`${cardInner} p-4`}>
              <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-purple-text">
                    {goal.name}
                    {goal.is_complete && (
                      <span className="ml-2 inline-flex rounded-md bg-emerald-400/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                        Complete
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-purple-muted">
                    {money(goal.current_amount)} of {money(goal.target_amount)}
                    {goal.deadline ? ` · due ${goal.deadline}` : ''}
                  </p>
                </div>
                <p className={`text-sm font-semibold ${goal.is_complete ? 'text-emerald-400' : 'text-purple-primary-light'}`}>
                  {goal.progress_pct}%
                </p>
              </div>

              <ProgressBar pct={goal.progress_pct} complete={goal.is_complete} />

              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-purple-muted">
                <span>
                  {goal.is_complete
                    ? 'Target reached'
                    : `${money(goal.remaining)} remaining`}
                </span>
                <div className="flex flex-wrap gap-2">
                  {!goal.is_complete && (
                    <button
                      type="button"
                      className="font-medium text-purple-primary-light transition hover:text-purple-text"
                      onClick={() => {
                        setContributeId(goal.id);
                        setContributeAmount('');
                        setFormOpen(false);
                      }}
                    >
                      Add
                    </button>
                  )}
                  <button
                    type="button"
                    className="font-medium text-purple-soft transition hover:text-purple-text"
                    onClick={() => startEdit(goal)}
                  >
                    Edit
                  </button>
                  {goal.is_complete && (
                    <button
                      type="button"
                      className="font-medium text-purple-soft transition hover:text-purple-text"
                      onClick={() => archiveGoal(goal)}
                    >
                      Archive
                    </button>
                  )}
                  <button
                    type="button"
                    className="font-medium text-red-300/80 transition hover:text-red-300"
                    onClick={() => removeGoal(goal)}
                  >
                    Delete
                  </button>
                </div>
              </div>

              {contributeId === goal.id && (
                <form onSubmit={submitContribute} className="mt-3 flex flex-wrap items-end gap-2 border-t border-purple-primary/10 pt-3">
                  <div className="min-w-[140px] flex-1">
                    <label className={statLabel} htmlFor={`contribute-${goal.id}`}>Contribution</label>
                    <input
                      id={`contribute-${goal.id}`}
                      className={input}
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={contributeAmount}
                      onChange={(e) => setContributeAmount(e.target.value)}
                      placeholder="500"
                      required
                      autoFocus
                    />
                  </div>
                  <button type="submit" className={`${btnPrimary} !px-3 !py-2 !text-xs`} disabled={saving}>
                    Save
                  </button>
                  <button
                    type="button"
                    className="rounded-xl px-3 py-2 text-xs font-medium text-purple-soft transition hover:bg-purple-primary/10"
                    onClick={() => setContributeId(null)}
                  >
                    Cancel
                  </button>
                </form>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
