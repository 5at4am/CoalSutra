/* Shared interactive styles — one source of truth for button/input look. */

export const btnBase =
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45";

export const btnPrimary = `${btnBase} bg-accent px-4 py-2 text-white hover:bg-accent-strong`;

export const btnSecondary = `${btnBase} border border-coal-300 bg-white px-4 py-2 text-ink-muted hover:border-coal-400 hover:bg-canvas hover:text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:hover:text-white`;

export const btnGhost = `${btnBase} px-2.5 py-1.5 text-ink-muted hover:bg-coal-100 hover:text-ink dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white`;

export const inputBase =
  "w-full rounded-lg border border-coal-300 bg-white px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-ink-muted/70 focus:border-accent-ring dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-slate-500";

export const cardBase =
  "rounded-2xl border border-coal-200 bg-white shadow-card dark:border-slate-700 dark:bg-slate-900";