import { CATEGORIES } from './categorize';

function mergeExpenseDay(prev, day, expense) {
  const next = { ...prev };
  if (expense === null) {
    delete next[day];
  } else if (expense) {
    next[day] = expense;
  }
  return next;
}

function countDaysLogged(expenses) {
  return Object.values(expenses).filter((entry) => Number(entry?.total) > 0).length;
}

export function patchComparisonFromTotals(comparison, totals, expenses) {
  if (!comparison?.current) return comparison;

  const allowance = Number(totals.spent) + Number(totals.remaining);
  const current = {
    ...comparison.current,
    allowance,
    spent: Number(totals.spent),
    remaining: Number(totals.remaining),
    breakdown: Object.fromEntries(
      CATEGORIES.map((category) => [category, Number(totals[category]) || 0]),
    ),
    days_logged: countDaysLogged(expenses),
    has_budget: allowance > 0,
  };
  const previous = comparison.previous;
  const spentDelta = current.spent - previous.spent;
  const allowanceDelta = current.allowance - previous.allowance;
  let spentPctChange = null;
  if (previous.has_budget && previous.spent > 0) {
    spentPctChange = Math.round((spentDelta / previous.spent) * 1000) / 10;
  }
  return {
    current,
    previous,
    delta: {
      spent: spentDelta,
      allowance: allowanceDelta,
      spent_pct_change: spentPctChange,
    },
  };
}

export function applyMutationPatch(setExpenses, setTotals, setComparison, patch, extras = {}) {
  const { day, expense, totals, comparison, category_status, category_limits } = patch;
  const { setCategoryStatus, setCategoryLimits } = extras;

  setExpenses((prev) => {
    const next = mergeExpenseDay(prev, day, expense);
    if (totals && !comparison) {
      setComparison((cmp) => patchComparisonFromTotals(cmp, totals, next));
    }
    return next;
  });
  if (totals) setTotals(totals);
  if (comparison) setComparison(comparison);
  if (category_status && setCategoryStatus) setCategoryStatus(category_status);
  if (category_limits && setCategoryLimits) setCategoryLimits(category_limits);
  if (patch.category_rules && extras.setCategoryRules) extras.setCategoryRules(patch.category_rules);
}

export function patchAllowance(allowance, totals, expenses, comparison) {
  const newTotals = {
    ...totals,
    remaining: allowance - Number(totals.spent),
  };
  return {
    allowance,
    totals: newTotals,
    comparison: patchComparisonFromTotals(comparison, newTotals, expenses),
  };
}

export function applyDashboardData(data, {
  setUsername,
  setWeekInfo,
  setAllowance,
  setExpenses,
  setTotals,
  setComparison,
  setScreen,
  setCategoryStatus,
  setCategoryLimits,
  setCategoryRules,
}) {
  setUsername?.(data.username);
  setWeekInfo(data.week_info);
  setComparison(data.comparison);
  if (setCategoryRules && data.category_rules) setCategoryRules(data.category_rules);
  if (data.budget.allowance > 0) {
    setAllowance(data.budget.allowance);
    setExpenses(data.budget.expenses || {});
    setTotals(data.budget.totals);
    if (setCategoryStatus && data.budget.category_status) {
      setCategoryStatus(data.budget.category_status);
    }
    if (setCategoryLimits && data.budget.category_limits) {
      setCategoryLimits(data.budget.category_limits);
    }
    setScreen('tracker');
  }
}
