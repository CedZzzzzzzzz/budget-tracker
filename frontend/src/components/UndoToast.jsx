import { useEffect } from 'react';

export default function UndoToast({ item, onUndo, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 8000);
    return () => clearTimeout(timer);
  }, [item, onDismiss]);

  if (!item) return null;

  return (
    <div className="glass-card fixed bottom-6 left-1/2 z-[2100] flex -translate-x-1/2 items-center gap-3 rounded-xl px-4 py-3">
      <span className="text-sm text-purple-text-dim">
        Removed <span className="font-medium text-purple-text">{item.name}</span>
      </span>
      <button
        type="button"
        className="rounded-lg bg-purple-primary px-3 py-1 text-xs font-medium text-white transition hover:bg-purple-primary-light"
        onClick={onUndo}
      >
        Undo
      </button>
      <button
        type="button"
        className="text-purple-muted transition hover:text-purple-text"
        onClick={onDismiss}
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
