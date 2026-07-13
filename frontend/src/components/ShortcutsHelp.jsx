import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { card } from '../utils/theme';

export const EXPENSE_SHORTCUTS = [
  { keys: ['N'], description: 'Focus item name' },
  { keys: ['A'], description: 'Focus amount' },
  { keys: ['1', '7'], description: 'Select day (Sun–Sat)', range: true },
  { keys: ['Ctrl', 'Enter'], description: 'Add expense', join: true },
  { keys: ['Esc'], description: 'Clear form / close' },
  { keys: ['?'], description: 'Show this help' },
];

function Kbd({ children }) {
  return (
    <kbd className="inline-flex min-w-[1.5rem] items-center justify-center rounded-md border border-purple-primary/25 bg-purple-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-medium text-purple-primary-light">
      {children}
    </kbd>
  );
}

export default function ShortcutsHelp({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[2100] flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
      style={{ animation: 'fadeIn 0.2s ease-out' }}
    >
      <div
        className={`${card} w-full max-w-sm overflow-hidden rounded-b-none rounded-t-3xl sm:rounded-3xl`}
        onClick={(e) => e.stopPropagation()}
        style={{ animation: 'fadeIn 0.28s cubic-bezier(0.16,1,0.3,1)' }}
        role="dialog"
        aria-labelledby="shortcuts-title"
      >
        <div className="flex items-start justify-between gap-4 border-b border-purple-primary/10 px-5 py-4">
          <div>
            <h3 id="shortcuts-title" className="text-base font-semibold tracking-tight text-purple-text">
              Keyboard shortcuts
            </h3>
            <p className="mt-0.5 text-xs text-purple-muted">Fast expense entry on Weekly</p>
          </div>
          <button
            type="button"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-purple-muted transition hover:bg-purple-primary/10 hover:text-purple-text"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <ul className="space-y-2.5 px-5 py-4">
          {EXPENSE_SHORTCUTS.map((row) => (
            <li key={row.description} className="flex items-center justify-between gap-3">
              <span className="text-sm text-purple-soft">{row.description}</span>
              <span className="flex items-center gap-1">
                {row.range ? (
                  <>
                    <Kbd>{row.keys[0]}</Kbd>
                    <span className="text-[10px] text-purple-muted">–</span>
                    <Kbd>{row.keys[1]}</Kbd>
                  </>
                ) : row.join ? (
                  <>
                    <Kbd>{row.keys[0]}</Kbd>
                    <span className="text-[10px] text-purple-muted">+</span>
                    <Kbd>{row.keys[1]}</Kbd>
                  </>
                ) : (
                  row.keys.map((key) => <Kbd key={key}>{key}</Kbd>)
                )}
              </span>
            </li>
          ))}
        </ul>
        <p className="border-t border-purple-primary/10 px-5 py-3 text-[11px] text-purple-muted">
          Shortcuts are ignored while typing in a field (except Esc and Ctrl+Enter).
        </p>
      </div>
    </div>,
    document.body,
  );
}

export function isEditableTarget(target) {
  if (!target || !(target instanceof Element)) return false;
  const el = target.closest('input, textarea, select, [contenteditable="true"]');
  return Boolean(el);
}
