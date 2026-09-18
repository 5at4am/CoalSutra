"use client";

import { useEffect } from "react";
import type { EvidenceCitation } from "./SourceChip";

type SourceEvidencePanelProps = {
  citation: EvidenceCitation | null;
  onClose: () => void;
};

export default function SourceEvidencePanel({
  citation,
  onClose,
}: SourceEvidencePanelProps) {
  useEffect(() => {
    if (!citation) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [citation, onClose]);

  if (!citation) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        aria-label="Close sources panel"
        onClick={onClose}
        className="absolute inset-0 bg-coal-950/40 backdrop-blur-[2px]"
      />
      <aside className="relative z-10 flex h-full w-full max-w-md animate-slide-in-right flex-col border-l border-coal-300 bg-white shadow-drawer dark:border-slate-700 dark:bg-slate-900">
        <header className="flex items-center justify-between border-b border-coal-200 px-5 py-4 dark:border-slate-800">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-source">
              Source evidence
            </p>
            <h3 className="mt-0.5 text-sm font-semibold text-coal-950 dark:text-slate-100">
              {citation.document_name}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md px-2 py-1 text-base text-coal-400 transition-colors hover:bg-coal-100 hover:text-coal-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <span className="inline-block rounded-md bg-source-light px-2 py-1 text-xs font-medium text-source-dark dark:bg-source/15 dark:text-emerald-300">
            Page {citation.page_number}
          </span>
          <p className="mt-4 text-[15px] leading-relaxed text-coal-800 dark:text-slate-200">
            &ldquo;{citation.snippet}&rdquo;
          </p>
        </div>
        <footer className="border-t border-coal-200 px-5 py-3 text-xs text-coal-400 dark:border-slate-800 dark:text-slate-500">
          Page-level traceability to the original scanned document.
        </footer>
      </aside>
    </div>
  );
}