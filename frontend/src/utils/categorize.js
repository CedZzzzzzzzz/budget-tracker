import data from '@shared/categories.json';

export const CATEGORIES = data.categories;
export const CATEGORY_LABELS = data.labels;
export const CATEGORY_ICONS = data.icons;
export const CATEGORY_COLORS = data.colors;

export const CUSTOM_CATEGORY_COLORS = [
  '#94a3b8',
  '#38bdf8',
  '#34d399',
  '#fbbf24',
  '#fb923c',
  '#f472b6',
  '#a78bfa',
  '#f87171',
];

export function mergeCategoryMeta(customCategories = []) {
  const categories = [...CATEGORIES];
  const labels = { ...CATEGORY_LABELS };
  const colors = { ...CATEGORY_COLORS };

  for (const custom of customCategories) {
    if (!custom?.slug) continue;
    if (!categories.includes(custom.slug)) categories.push(custom.slug);
    labels[custom.slug] = custom.label || custom.slug;
    colors[custom.slug] = custom.color || CATEGORY_COLORS.other;
  }

  return { categories, labels, colors };
}

export function categoryColor(category, colors = CATEGORY_COLORS) {
  return colors[category] || CATEGORY_COLORS.other;
}

export function categoryLabel(category, labels = CATEGORY_LABELS) {
  return labels[category] || category;
}

export function categoryTintStyle(category, {
  bgAlpha = 0.15,
  borderAlpha = 0.28,
  colors = CATEGORY_COLORS,
} = {}) {
  const hex = categoryColor(category, colors);
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

export function categorizeItem(name, userRules = null, allowedCategories = CATEGORIES) {
  const lower = (name || '').toLowerCase().trim();
  if (!lower) return 'other';

  const tokens = tokenize(lower);
  const allowed = new Set(allowedCategories || CATEGORIES);
  if (userRules?.length) {
    for (const rule of userRules) {
      const pattern = (rule.pattern || '').toLowerCase().trim();
      const category = rule.category;
      if (!pattern || !allowed.has(category)) continue;
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
