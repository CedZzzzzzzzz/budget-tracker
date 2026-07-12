import { CATEGORY_LABELS, categoryTintStyle } from '../utils/categorize';
import CategoryIcon from './CategoryIcon';

export default function CategoryBadge({ category, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${className}`}
      style={categoryTintStyle(category)}
    >
      <CategoryIcon category={category} className="h-3.5 w-3.5 opacity-90" />
      {CATEGORY_LABELS[category]}
    </span>
  );
}

export function CategoryIconBox({ category, className = '' }) {
  return (
    <span
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${className}`}
      style={categoryTintStyle(category, { bgAlpha: 0.18, borderAlpha: 0.32 })}
      title={CATEGORY_LABELS[category]}
    >
      <CategoryIcon category={category} className="h-[18px] w-[18px]" />
    </span>
  );
}
