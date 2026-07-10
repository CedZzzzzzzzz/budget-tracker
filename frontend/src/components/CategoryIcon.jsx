const svgBase = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

const ICONS = {
  fare: (
    <svg {...svgBase}>
      <path d="M4 16h16" />
      <path d="M5 16l1.5-5h11L19 16" />
      <circle cx="7.5" cy="16.5" r="1.5" />
      <circle cx="16.5" cy="16.5" r="1.5" />
      <path d="M7 11h3M14 11h3" />
    </svg>
  ),
  food: (
    <svg {...svgBase}>
      <path d="M6 4v8" />
      <path d="M6 8h2" />
      <path d="M8 4v8" />
      <path d="M14 4c0 2 1.5 3 1.5 5v7" />
      <path d="M17.5 16H12" />
    </svg>
  ),
  groceries: (
    <svg {...svgBase}>
      <path d="M6 10h15l-1.5 7H7.5L6 10Z" />
      <path d="M6 10 5 6H3" />
      <path d="M9 14h6" />
    </svg>
  ),
  bills: (
    <svg {...svgBase}>
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
      <path d="M13 2v7h7" />
      <path d="M8 13h8M8 17h5" />
      <path d="M16 13h.01" />
    </svg>
  ),
  shopping: (
    <svg {...svgBase}>
      <path d="M6 8h15l-1.5 9H7.5L6 8Z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </svg>
  ),
  entertainment: (
    <svg {...svgBase}>
      <path d="M4 8h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8Z" />
      <path d="m10 12 6 3-6 3v-6Z" />
      <path d="M8 4h8" />
    </svg>
  ),
  health: (
    <svg {...svgBase}>
      <path d="M12 21s-6-4.35-6-9a4 4 0 0 1 7-2.35A4 4 0 0 1 18 12c0 4.65-6 9-6 9Z" />
      <path d="M12 9v4M10 11h4" />
    </svg>
  ),
  other: (
    <svg {...svgBase}>
      <circle cx="12" cy="12" r="8" />
      <circle cx="9" cy="10" r="1" fill="currentColor" stroke="none" />
      <circle cx="15" cy="10" r="1" fill="currentColor" stroke="none" />
      <path d="M9.5 15c.9.75 2.1.75 3 0" />
    </svg>
  ),
};

export default function CategoryIcon({ category, className = 'h-4 w-4', size }) {
  const icon = ICONS[category] || ICONS.other;
  const style = size ? { width: size, height: size } : undefined;
  return (
    <span className={`inline-flex shrink-0 items-center justify-center ${className}`} style={style} aria-hidden="true">
      {icon}
    </span>
  );
}

export { ICONS as CATEGORY_SVG_ICONS };
