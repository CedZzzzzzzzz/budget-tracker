import data from '@shared/categories.json';

export const CATEGORIES = data.categories;
export const CATEGORY_LABELS = data.labels;
export const CATEGORY_ICONS = data.icons;
export const CATEGORY_COLORS = data.colors;

export function categoryColor(category) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.other;
}

export function categoryTintStyle(category, { bgAlpha = 0.15, borderAlpha = 0.28 } = {}) {
  const hex = categoryColor(category);
  return {
    color: hex,
    backgroundColor: hexToRgba(hex, bgAlpha),
    borderColor: hexToRgba(hex, borderAlpha),
  };
}

function hexToRgba(hex, alpha) {
  const raw = hex.replace('#', '');
  const full = raw.length === 3
    ? raw.split('').map((c) => c + c).join('')
    : raw;
  const n = Number.parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

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
