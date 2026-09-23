"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiUpload } from "@/lib/api";
import Icon from "@/components/Icon";
import PageHeader, { SectionHeader } from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import AlertBanner from "@/components/AlertBanner";
import EmptyState from "@/components/EmptyState";
import { btnSecondary } from "@/lib/ui";

type DocStatus = "pending" | "processing" | "processed" | "failed";

type DocumentItem = {
  id: number;
  filename: string;
  source_type: string;
  upload_date: string;
  status: DocStatus;
  fact_count: number;
};

const ACCEPT = ".pdf,.csv,.xlsx,.xls,.ods,.png,.jpg,.jpeg,.tif,.tiff";

const FORMATS = ["PDF", "CSV", "XLSX", "XLS", "ODS", "PNG", "JPG", "TIFF"];

const STATUS_LABEL: Record<DocStatus, string> = {
  pending: "pending",
  processing: "processing",
  processed: "processed",
  failed: "failed",
};

const STATUS_TONE: Record<DocStatus, "neutral" | "warning" | "success" | "danger"> = {
  pending: "neutral",
  processing: "warning",
  processed: "success",
  failed: "danger",
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function IngestPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      setError(null);
      setDocs(await apiGet<DocumentItem[]>("/api/v1/documents"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents.");
    }
  }, []);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  const hasActive = (docs ?? []).some(
    (d) => d.status === "pending" || d.status === "processing"
  );

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => {
      void loadDocs();
    }, 2000);
    return () => clearInterval(timer);
  }, [hasActive, loadDocs]);

  async function uploadFiles(files: File[]) {
    for (const file of files) {
      if (uploading.includes(file.name)) continue;
      setUploading((prev) => [...prev, file.name]);
      setError(null);
      setFeedback(null);
      try {
        const doc = await apiUpload<DocumentItem>("/api/v1/documents/upload", file);
        setDocs((prev) => {
          const rest = (prev ?? []).filter((d) => d.id !== doc.id);
          return [doc, ...rest];
        });
        setFeedback(`Queued ${file.name} for ingestion.`);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : `Failed to upload ${file.name}.`
        );
      } finally {
        setUploading((prev) => prev.filter((n) => n !== file.name));
      }
    }
    void loadDocs();
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    void uploadFiles(Array.from(e.dataTransfer.files));
  }

  const processed = (docs ?? []).filter((d) => d.status === "processed").length;
  const failed = (docs ?? []).filter((d) => d.status === "failed").length;

  return (
    <main className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6">
      <PageHeader
        title="Ingest"
        purpose="Upload CIL/CMPDI documents — scanned or born-digital PDFs, images,
            spreadsheets — and the pipeline extracts cited facts from them."
        actions={
          <>
            <button onClick={() => void loadDocs()} className={`${btnSecondary} px-3 py-2`}>
              <Icon name="refresh" size={15} />
              Refresh
            </button>
          </>
        }
        context={
          docs && (
            <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-muted dark:text-slate-500">
              <StatusBadge label={`${processed} processed`} tone="success" dot />
              {failed > 0 && <StatusBadge label={`${failed} failed`} tone="danger" dot />}
              <StatusBadge
                label={`${(docs ?? []).filter((d) => d.status === "processing" || d.status === "pending").length} in queue`}
                tone="neutral"
                dot
              />
            </p>
          )
        }
      />

      {/* ---------- dropzone ---------- */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload documents"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mt-5 cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ring sm:p-12 ${
          dragOver
            ? "border-accent-ring bg-accent-faint dark:border-amber-500 dark:bg-accent/10"
            : "border-coal-300 bg-white hover:border-coal-400 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-500"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(e) => {
            if (e.target.files?.length) {
              void uploadFiles(Array.from(e.target.files));
              e.target.value = "";
            }
          }}
        />
        <span
          className={`mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl transition-colors ${
            dragOver
              ? "bg-accent text-white dark:text-amber-300"
              : "bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400"
          }`}
        >
          <Icon name="upload" size={22} />
        </span>
        <p className="mt-4 text-sm font-medium text-ink dark:text-slate-200">
          {dragOver
            ? "Release to upload"
            : "Drop documents here or click to browse"}
        </p>
        <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
          Multiple files allowed — they are queued and processed in order.
        </p>
        <ul className="mx-auto mt-4 flex max-w-2xl flex-wrap items-center justify-center gap-1.5">
          {FORMATS.map((f) => (
            <li
              key={f}
              className="rounded-md border border-coal-200 bg-canvas px-2 py-0.5 font-mono text-[11px] text-ink-muted dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
            >
              {f}
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-ink-muted dark:text-slate-500">
        Scanned PDFs/images need the OCR binary installed; born-digital PDFs and
        spreadsheets extract without it. Each extracted figure carries its source
        document and page.
      </p>

      {/* ---------- feedback ---------- */}
      {uploading.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2" aria-live="polite">
          {uploading.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1.5 rounded-full border border-coal-200 bg-white px-2.5 py-1 text-xs font-medium text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              <Icon name="refresh" size={12} className="animate-spin text-accent" />
              Uploading {name}…
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-4">
          <AlertBanner tone="error">{error}</AlertBanner>
        </div>
      )}
      {feedback && (
        <div className="mt-4">
          <AlertBanner tone="success">{feedback}</AlertBanner>
        </div>
      )}

      {/* ---------- document list ---------- */}
      <section className="mt-8">
        <SectionHeader
          title="Documents"
          icon="file"
          meta={
            <span className="rounded-full bg-coal-100 px-2.5 py-0.5 text-xs font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-400">
              {docs?.length ?? "…"}
            </span>
          }
        />

        {docs === null ? (
          <div className="mt-3 flex items-center justify-center gap-2 rounded-2xl border border-coal-200 bg-white p-10 text-sm text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            <Icon name="refresh" size={14} className="animate-spin" />
            Loading documents…
          </div>
        ) : docs.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              icon="upload"
              title="Nothing ingested yet"
              body="Upload a document above — extracted facts show up here, then become answerable in Chat and reviewable in the Review Queue."
              action={
                <button
                  onClick={() => inputRef.current?.click()}
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
                >
                  Choose a file
                </button>
              }
            />
          </div>
        ) : (
          <div className="mt-3 overflow-hidden rounded-2xl border border-coal-200 bg-white shadow-card dark:border-slate-700 dark:bg-slate-900">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-coal-200 text-xs uppercase tracking-wide text-ink-muted dark:border-slate-700 dark:text-slate-500">
                  <th scope="col" className="px-4 py-2.5 font-medium">Document</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">Source</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Uploaded</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Facts</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-coal-100 dark:divide-slate-800">
                {docs.map((doc) => (
                  <tr key={doc.id} className="transition-colors hover:bg-canvas dark:hover:bg-slate-800/60">
                    <td className="max-w-0 px-4 py-3">
                      <p className="flex items-center gap-2 truncate font-medium text-ink dark:text-slate-100">
                        <Icon name="file" size={14} className="shrink-0 text-coal-400 dark:text-slate-500" />
                        <span className="truncate">{doc.filename}</span>
                      </p>
                      <p className="mt-0.5 text-xs text-ink-muted dark:text-slate-500 md:hidden">
                        {doc.source_type} · {formatDate(doc.upload_date)}
                      </p>
                    </td>
                    <td className="hidden px-4 py-3 text-sm text-ink-muted dark:text-slate-400 sm:table-cell">
                      {doc.source_type}
                    </td>
                    <td className="hidden px-4 py-3 text-sm text-ink-muted dark:text-slate-400 md:table-cell">
                      {formatDate(doc.upload_date)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-ink dark:text-slate-200">
                      {doc.fact_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="inline-flex items-center justify-end gap-1.5">
                        {doc.status === "processing" && (
                          <Icon name="refresh" size={12} className="animate-spin text-gap dark:text-amber-300" />
                        )}
                        <StatusBadge tone={STATUS_TONE[doc.status]} label={STATUS_LABEL[doc.status]} dot />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}