import { useMemo, useState, useId } from 'react';
import { categoryColor, categoryLabel } from '../utils/categorize';
import { useCategories } from './CategoriesContext';
import CategoryIcon from './CategoryIcon';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function ChartLabel({ children }) {
  return (
    <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-purple-muted">
      {children}
    </p>
  );
}

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? 0 : 1;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} L ${cx} ${cy} Z`;
}

export function CategoryDonutChart({ totals }) {
  const [active, setActive] = useState(null);
  const { categories, labels, colors } = useCategories();

  const segments = useMemo(() => {
    const items = categories
      .map((category) => ({
        category,
        label: categoryLabel(category, labels),
        value: Number(totals[category]) || 0,
        color: categoryColor(category, colors),
      }))
      .filter((item) => item.value > 0);
    const total = items.reduce((sum, item) => sum + item.value, 0);
    let angle = 0;
    return items.map((item) => {
      const sweep = total ? (item.value / total) * 360 : 0;
      const segment = { ...item, start: angle, end: angle + sweep };
      angle += sweep;
      return segment;
    });
  }, [totals, categories, labels, colors]);

  const spent = Number(totals.spent) || 0;
  const hovered = segments.find((s) => s.category === active);

  if (!segments.length) {
    return (
      <div className="glass-inner flex h-full min-h-[200px] items-center justify-center rounded-xl p-4 text-sm text-purple-muted">
        Add expenses to see category breakdown
      </div>
    );
  }

  return (
    <div className="glass-inner flex h-full flex-col rounded-xl p-4">
      <ChartLabel>By category</ChartLabel>
      <div className="flex flex-1 flex-col items-center justify-center gap-4 sm:flex-row sm:items-center">
        <div className="relative shrink-0">
          <svg width="132" height="132" viewBox="0 0 160 160">
            {segments.map((seg) => (
              <path
                key={seg.category}
                d={describeArc(80, 80, 64, seg.start, seg.end - 0.4)}
                fill={seg.color}
                opacity={active && active !== seg.category ? 0.35 : 1}
                className="cursor-pointer transition-opacity"
                onMouseEnter={() => setActive(seg.category)}
                onMouseLeave={() => setActive(null)}
                onClick={() => setActive(active === seg.category ? null : seg.category)}
              />
            ))}
            <circle cx="80" cy="80" r="38" className="fill-purple-deep/90" />
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-base font-semibold text-purple-text">
              ₱{(hovered?.value ?? spent).toFixed(0)}
            </span>
            <span className="max-w-[72px] truncate text-[10px] text-purple-muted">
              {hovered?.label ?? 'Total spent'}
            </span>
          </div>
        </div>
        <div className="grid w-full flex-1 grid-cols-1 gap-1.5 sm:grid-cols-2">
          {segments.map((seg) => (
            <button
              key={seg.category}
              type="button"
              className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs transition ${
                active === seg.category
                  ? 'border-purple-primary/40 bg-purple-primary/15 text-purple-text'
                  : 'border-white/[0.06] bg-white/[0.03] text-purple-soft hover:border-purple-primary/25'
              }`}
              onMouseEnter={() => setActive(seg.category)}
              onMouseLeave={() => setActive(null)}
              onClick={() => setActive(active === seg.category ? null : seg.category)}
            >
              <span className="shrink-0" style={{ color: seg.color }}>
                <CategoryIcon category={seg.category} className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1 truncate">{seg.label}</span>
              <span className="shrink-0 font-medium text-purple-text">₱{seg.value.toFixed(0)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function WeekComparisonChart({ comparison }) {
  const [hovered, setHovered] = useState(null);

  if (!comparison?.current) return null;

  const bars = [
    {
      key: 'current',
      label: 'This week',
      spent: comparison.current.spent,
      allowance: comparison.current.allowance,
      spentColor: '#b982ff',
    },
    {
      key: 'previous',
      label: 'Last week',
      spent: comparison.previous.spent,
      allowance: comparison.previous.allowance,
      spentColor: '#9d4edd',
      hidden: !comparison.previous.has_budget,
    },
  ].filter((bar) => !bar.hidden);

  const maxVal = Math.max(1, ...bars.flatMap((b) => [b.spent, b.allowance]));

  return (
    <div className="glass-inner flex h-full flex-col rounded-xl p-4">
      <ChartLabel>Week over week</ChartLabel>
      <div className="flex flex-1 flex-col justify-center">
        <div className="flex items-end justify-around gap-4" style={{ height: 120 }}>
          {bars.map((bar) => {
            const spentH = (bar.spent / maxVal) * 100;
            const allowH = (bar.allowance / maxVal) * 100;
            const active = hovered === bar.key;
            return (
              <div
                key={bar.key}
                className="flex flex-col items-center gap-2"
                onMouseEnter={() => setHovered(bar.key)}
                onMouseLeave={() => setHovered(null)}
              >
                <div className="flex h-[96px] items-end justify-center gap-1.5">
                  <div
                    className="w-5 rounded-t-md bg-purple-primary/20"
                    style={{ height: `${allowH}%`, minHeight: bar.allowance > 0 ? 4 : 0 }}
                    title={`Allowance ₱${bar.allowance.toFixed(0)}`}
                  />
                  <div
                    className="w-5 rounded-t-md transition-opacity"
                    style={{
                      height: `${spentH}%`,
                      minHeight: bar.spent > 0 ? 6 : 0,
                      backgroundColor: bar.spentColor,
                      opacity: hovered && !active ? 0.45 : 1,
                    }}
                    title={`Spent ₱${bar.spent.toFixed(0)}`}
                  />
                </div>
                <div className="text-center">
                  <p className="text-xs font-medium text-purple-text">{bar.label}</p>
                  {active && (
                    <p className="mt-0.5 text-[10px] text-purple-muted">
                      ₱{bar.spent.toFixed(0)} / ₱{bar.allowance.toFixed(0)}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap justify-center gap-3 text-[10px] text-purple-muted">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm bg-purple-primary/20" />
            Allowance
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm bg-purple-primary-light" />
            This week
          </span>
          {bars.length > 1 && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-sm bg-purple-primary" />
              Last week
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function SpendingByDayChart({ expenses, todayIndex = 6 }) {
  const [active, setActive] = useState(null);
  const chartId = useId().replace(/:/g, '');

  const data = useMemo(
    () => DAYS.map((day, i) => ({
      day,
      short: day.slice(0, 3),
      value: Number(expenses[day]?.total) || 0,
      isToday: i === todayIndex,
      isFuture: i > todayIndex,
    })),
    [expenses, todayIndex],
  );

  const max = Math.max(1, ...data.map((d) => d.value));
  const weekTotal = data.reduce((s, d) => s + d.value, 0);
  const activeDay = active != null ? data[active] : null;

  const W = 100;
  const H = 32;
  const pad = { top: 2, right: 1.5, bottom: 2, left: 1.5 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;

  const points = data.map((d, i) => {
    const x = pad.left + (i / 6) * chartW;
    return {
      ...d,
      x,
      xPct: (x / W) * 100,
      y: pad.top + chartH - (d.value / max) * chartH,
    };
  });

  const linePoints = points.filter((p) => !p.isFuture);

  const smoothPath = (pts) => {
    if (pts.length < 2) return pts.length ? `M ${pts[0].x} ${pts[0].y}` : '';
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i += 1) {
      const p0 = pts[i - 1] || pts[i];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2] || p2;
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  };

  const linePath = smoothPath(linePoints);
  const lastPoint = linePoints[linePoints.length - 1];
  const areaPath = linePath && lastPoint
    ? `${linePath} L ${lastPoint.x} ${pad.top + chartH} L ${linePoints[0].x} ${pad.top + chartH} Z`
    : '';

  return (
    <div className="daily-line-chart glass-inner rounded-xl px-3 py-2.5 sm:px-4">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <ChartLabel>Daily spending</ChartLabel>
        <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-[10px] text-purple-muted">
          {activeDay
            ? `${activeDay.short} ₱${activeDay.value.toFixed(0)}`
            : `₱${weekTotal.toFixed(0)} week`}
        </span>
      </div>

      <div className="daily-line-chart__plot relative w-full">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="daily-line-chart__svg absolute inset-x-0 top-0 block w-full"
          style={{ height: 'calc(100% - 14px)' }}
          preserveAspectRatio="none"
          role="img"
          aria-label="Daily spending line chart"
        >
          <defs>
            <linearGradient id={`${chartId}-fill`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" className="daily-line-chart__fill-top" />
              <stop offset="55%" className="daily-line-chart__fill-mid" />
              <stop offset="100%" className="daily-line-chart__fill-bottom" />
            </linearGradient>
            <filter id={`${chartId}-glow`} x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="0.45" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <line
            x1={pad.left}
            y1={pad.top + chartH}
            x2={pad.left + chartW}
            y2={pad.top + chartH}
            className="daily-line-chart__baseline"
            vectorEffect="non-scaling-stroke"
          />

          {areaPath && (
            <path
              d={areaPath}
              fill={`url(#${chartId}-fill)`}
              className="daily-line-chart__area"
            />
          )}

          {linePath && (
            <>
              <path
                d={linePath}
                fill="none"
                className="daily-line-chart__glow-outer"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
              <path
                d={linePath}
                fill="none"
                className="daily-line-chart__glow-mid"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
              <path
                d={linePath}
                fill="none"
                className="daily-line-chart__glow-core"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter={`url(#${chartId}-glow)`}
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}

          {points.map((p, i) => {
            const isActive = active === i;
            const showDot = isActive || p.isToday || (p.value > 0 && !p.isFuture);
            return (
              <g
                key={p.day}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                className={p.isFuture ? 'opacity-30' : 'cursor-pointer'}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="2.5"
                  fill="transparent"
                  vectorEffect="non-scaling-stroke"
                />
                {showDot && (
                  <>
                    {isActive && (
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r="1.1"
                        className="daily-line-chart__dot-halo"
                        vectorEffect="non-scaling-stroke"
                      />
                    )}
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r={isActive ? 0.65 : p.isToday ? 0.55 : 0.45}
                      className={`daily-line-chart__dot ${p.isToday ? 'daily-line-chart__dot--today' : ''} ${isActive ? 'daily-line-chart__dot--active' : ''}`}
                      vectorEffect="non-scaling-stroke"
                    />
                  </>
                )}
              </g>
            );
          })}
        </svg>

        <div className="absolute inset-x-0 bottom-0 h-[14px]">
          {points.map((p, i) => (
            <button
              key={p.day}
              type="button"
              style={{ left: `${p.xPct}%` }}
              className={`daily-line-chart__day absolute -translate-x-1/2 py-0.5 text-[9px] font-medium transition ${
                active === i
                  ? 'daily-line-chart__day--active'
                  : p.isToday
                    ? 'daily-line-chart__day--today'
                    : p.isFuture
                      ? 'daily-line-chart__day--future'
                      : ''
              }`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onClick={() => setActive(active === i ? null : i)}
            >
              {p.short}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
