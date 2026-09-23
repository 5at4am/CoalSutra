"use client";

import { useEffect } from "react";
import Icon from "@/components/Icon";
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

  useEffect(() => {
    if (!citation) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [citation]);

  if (!citation) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        aria-label="Close sources panel"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-slate-950/40 backdrop-blur-[2px]"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Source evidence — ${citation.document_name}`}
        className="relative z-10 flex h-full w-full max-w-md animate-slide-in-right flex-col border-l border-coal-200 bg-white shadow-panel dark:border-slate-700 dark:bg-slate-900"
      >
        <header className="flex items-start justify-between gap-3 border-b border-coal-200 px-5 py-4 dark:border-slate-800">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-source dark:text-emerald-300">
              <Icon name="source" size={13} />
              Source evidence
            </p>
            <h3 className="mt-1 break-words text-sm font-semibold text-ink dark:text-slate-100">
              {citation.document_name}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-coal-100 hover:text-ink dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            <Icon name="close" size={16} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <span className="inline-flex items-center gap-1 rounded-md bg-source-light px-2 py-1 text-xs font-medium text-source-dark dark:bg-source/15 dark:text-emerald-300">
            <Icon name="file" size={12} />
            Page {citation.page_number}
          </span>
          <blockquote className="mt-4 border-l-2 border-source/40 pl-4 text-[15px] leading-relaxed text-ink dark:text-slate-200">
            &ldquo;{citation.snippet}&rdquo;
          </blockquote>
        </div>
        <footer className="border-t border-coal-200 px-5 py-3 text-xs text-ink-muted dark:border-slate-800 dark:text-slate-500">
          Page-level traceability to the original scanned document.
        </footer>
      </aside>
    </div>
  );
}