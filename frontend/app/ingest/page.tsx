"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiUpload } from "@/lib/api";

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

const STATUS_BADGE: Record<DocStatus, string> = {
  pending: "bg-coal-100 dark:bg-slate-800 text-coal-700 dark:text-slate-300 dark:bg-slate-800 dark:text-slate-300",
  processing:
    "bg-gap-light text-gap dark:bg-gap/15 dark:text-amber-300",
  processed:
    "bg-source-light text-source-dark dark:bg-source/20 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
};

const STATUS_LABEL: Record<DocStatus, string> = {
  pending: "pending",
  processing: "processing…",
  processed: "processed",
  failed: "failed",
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
    <>
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-coal-950 dark:text-slate-100">Ingest</h1>
            <p className="mt-1 text-sm text-coal-500 dark:text-slate-400">
              Upload CIL/CMPDI documents — scanned or born-digital PDFs, images,
              spreadsheets — and the pipeline extracts cited facts from them.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-coal-400 dark:text-slate-500">
              {docs ? `${processed} processed` : ""}
              {failed > 0 ? ` · ${failed} failed` : ""}
            </span>
            <button
              onClick={() => void loadDocs()}
              className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm font-medium text-coal-600 dark:text-slate-300 transition-colors hover:border-coal-400 dark:hover:border-slate-600 hover:text-coal-900 dark:hover:text-white"
            >
              Refresh
            </button>
          </div>
        </header>

        {/* dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`mt-5 cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-colors ${
            dragOver
              ? "border-coal-500 bg-coal-50 dark:bg-slate-800"
              : "border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-coal-400 dark:hover:border-slate-600"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            hidden
            onChange={(e) => {
              if (e.target.files?.length) {
                void uploadFiles(Array.from(e.target.files));
                e.target.value = "";
              }
            }}
          />
          <div className="text-3xl font-semibold text-coal-300 dark:text-slate-600">+</div>
          <p className="mt-2 text-sm font-medium text-coal-800 dark:text-slate-200">
            Drop documents here or click to browse
          </p>
          <p className="mt-1 text-xs text-coal-400 dark:text-slate-500">
            PDF · CSV · XLSX · XLS · ODS · PNG · JPG · TIFF — multiple files allowed
          </p>
          <p className="mt-3 text-xs leading-relaxed text-coal-400 dark:text-slate-500">
            Scanned PDFs/images need the OCR binary installed; born-digital PDFs and
            spreadsheets extract without it.
          </p>
        </div>

        {uploading.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {uploading.map((name) => (
              <span
                key={name}
                className="rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300"
              >
                Uploading {name}…
              </span>
            ))}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400">
            {error}
          </div>
        )}
        {feedback && (
          <div className="mt-4 rounded-lg border border-source/20 bg-source-light px-3 py-2 text-sm text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300">
            {feedback}
          </div>
        )}

        {/* document table */}
        <section className="mt-8">
          <h2 className="text-base font-semibold text-coal-950 dark:text-slate-100">
            Documents
            <span className="ml-2 rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300">
              {docs?.length ?? "…"}
            </span>
          </h2>

          {docs === null ? (
            <div className="mt-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center text-sm text-coal-400 dark:text-slate-500 shadow-card">
              Loading documents…
            </div>
          ) : docs.length === 0 ? (
            <div className="mt-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-card">
              <h3 className="text-sm font-semibold text-coal-800 dark:text-slate-200">
                Nothing ingested yet
              </h3>
              <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                Upload a document above — extracted facts show up here, then
                become answerable in Chat and reviewable in the Review Queue.
              </p>
            </div>
          ) : (
            <ul className="mt-3 grid gap-2">
              {docs.map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 shadow-card"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-coal-950 dark:text-slate-100">
                      {doc.filename}
                    </p>
                    <p className="mt-0.5 text-xs text-coal-400 dark:text-slate-500">
                      #{doc.id} · {doc.source_type} · {formatDate(doc.upload_date)} ·{" "}
                      {doc.fact_count} fact{doc.fact_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_BADGE[doc.status]}`}
                  >
                    {STATUS_LABEL[doc.status]}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </>
  );
}