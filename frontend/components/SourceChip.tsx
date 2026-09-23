"use client";

import Icon from "@/components/Icon";

export type EvidenceCitation = {
  document_name: string;
  page_number: number;
  snippet: string;
};

type SourceChipProps = {
  citation: EvidenceCitation;
  onClick?: () => void;
};

export default function SourceChip({ citation, onClick }: SourceChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open source: ${citation.document_name} page ${citation.page_number}`}
      title={`${citation.document_name} · p.${citation.page_number}`}
      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-source/30 bg-source-light px-3 py-1 text-xs font-medium text-source-dark transition-colors hover:bg-source-chip dark:border-source/40 dark:bg-source/15 dark:text-emerald-300 dark:hover:bg-source/25"
    >
      <Icon name="file" size={12} className="shrink-0 opacity-80" />
      <span className="max-w-[16rem] truncate">{citation.document_name}</span>
      <span className="shrink-0 text-source-dark/70 dark:text-emerald-300/80">p.{citation.page_number}</span>
    </button>
  );
}