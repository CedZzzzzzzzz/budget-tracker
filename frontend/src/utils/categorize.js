import data from '@shared/categories.json';

export const CATEGORIES = data.categories;
export const CATEGORY_LABELS = data.labels;
export const CATEGORY_ICONS = data.icons;
export const CATEGORY_COLORS = data.colors;

const CATEGORY_KEYWORDS = data.keywords;
const CATEGORY_PRIORITY = data.priority;

function tokenize(lower) {
  return new Set(lower.match(/[a-z0-9]+/g) || []);
}

function matchUserRule(lower, tokens, pattern) {
  if (pattern.includes(' ') || pattern.includes('-')) {
    return lower.includes(pattern);
  }
  return tokens.has(pattern) || pattern === lower;
}

export function categorizeItem(name, userRules = null) {
  const lower = (name || '').toLowerCase().trim();
  if (!lower) return 'other';

  const tokens = tokenize(lower);
  if (userRules?.length) {
    for (const rule of userRules) {
      const pattern = (rule.pattern || '').toLowerCase().trim();
      const category = rule.category;
      if (!pattern || !CATEGORIES.includes(category)) continue;
      if (matchUserRule(lower, tokens, pattern)) return category;
    }
  }

  for (const category of CATEGORY_PRIORITY) {
    for (const kw of CATEGORY_KEYWORDS[category] || []) {
      if (kw.includes(' ') || kw.includes('-')) {
        if (lower.includes(kw)) return category;
      } else if (tokens.has(kw)) {
        return category;
      }
    }
  }
  return 'other';
}
