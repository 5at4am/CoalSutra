"use client";

import { useCallback, useEffect, useState } from "react";
import type { EvidenceCitation } from "@/components/SourceChip";
import SourceEvidencePanel from "@/components/SourceEvidencePanel";
import { apiGet, apiPost } from "@/lib/api";

type FactItem = {
  fact_id: number;
  entity: string;
  value: string;
  unit: string | null;
  date_reference: string | null;
  page_number: number | null;
  document_name: string;
  snippet: string;
  confidence: number;
};

type ConflictItem = {
  id: number;
  status: string;
  reason: string;
  resolution: string | null;
  resolved_by: string | null;
  fact_a: FactItem;
  fact_b: FactItem;
};

type DraftReportItem = {
  id: number;
  title: string;
  template_type: string;
  generated_at: string;
  status: string;
  summary: string;
};

type ReviewQueue = {
  conflicts: ConflictItem[];
  draft_reports: DraftReportItem[];
};

const DECISIONS = [
  { key: "fact_a", label: "Keep A", hint: "Trust the value on the left" },
  { key: "fact_b", label: "Keep B", hint: "Trust the value on the right" },
  { key: "both", label: "Keep both", hint: "Both figures are true (different scope)" },
  { key: "neither", label: "Neither", hint: "Send both facts back for review" },
] as const;

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

function confidenceColor(c: number): string {
  if (c >= 0.9) return "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-400";
  if (c >= 0.7) return "bg-gap-light text-gap dark:bg-gap/15 dark:text-amber-300";
  return "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400";
}

function FactPanel({ fact, side }: { fact: FactItem; side: "A" | "B" }) {
  const citation: EvidenceCitation = {
    document_name: fact.document_name,
    page_number: fact.page_number ?? 0,
    snippet: fact.snippet,
  };
  return (
    <figure className="flex-1 rounded-xl border border-coal-200 dark:border-slate-700 bg-coal-50/60 dark:bg-slate-800/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-coal-400 dark:text-slate-500">
          Fact {side}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${confidenceColor(fact.confidence)}`}
        >
          {Math.round(fact.confidence * 100)}% conf
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold text-coal-950 dark:text-slate-100">
        {fact.value}
        {fact.unit ? (
          <span className="ml-1 align-middle text-sm font-medium text-coal-400 dark:text-slate-500">
            {fact.unit}
          </span>
        ) : null}
      </p>
      <p className="mt-1 text-xs text-coal-400 dark:text-slate-500">
        {fact.entity}
        {fact.date_reference ? ` · ${String(fact.date_reference).slice(0, 4)}` : ""}
      </p>
      <blockquote className="mt-3 border-l-2 border-coal-200 dark:border-slate-700 pl-3 text-sm leading-relaxed text-coal-600 dark:text-slate-300">
        “{fact.snippet}”
      </blockquote>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <span className="rounded-full border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300">
          {fact.document_name}
        </span>
        {fact.page_number !== null && (
          <span className="rounded-full border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300">
            p.{fact.page_number}
          </span>
        )}
      </div>
    </figure>
  );
}

function ConflictCard({
  conflict,
  reviewer,
  onResolved,
  onCite,
  error,
  onError,
}: {
  conflict: ConflictItem;
  reviewer: string;
  onResolved: (c: ConflictItem, decision: string) => void;
  onCite: (c: EvidenceCitation) => void;
  error: string | null;
  onError: (msg: string | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);

  async function resolve(decision: string) {
    if (picked) return;
    setBusy(true);
    setPicked(decision);
    onError(null);
    try {
      await apiPost(`/api/v1/review/conflicts/${conflict.id}/resolve`, {
        decision,
        resolved_by: reviewer,
      });
      onResolved(conflict, decision);
    } catch (err) {
      setPicked(null);
      onError(err instanceof Error ? err.message : "Resolution failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-coal-900 dark:text-slate-100">{conflict.reason}</h3>
        <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-red-700 dark:bg-red-500/15 dark:text-red-400">
          open
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-4 md:flex-row">
        {[conflict.fact_a, conflict.fact_b].map((fact, i) => (
          <div key={fact.fact_id} className="flex flex-1 flex-col gap-1.5">
            <FactPanel fact={fact} side={i === 0 ? "A" : "B"} />
            <button
              type="button"
              onClick={() =>
                onCite({
                  document_name: fact.document_name,
                  page_number: fact.page_number ?? 0,
                  snippet: fact.snippet,
                })
              }
              className="self-end text-xs font-medium text-coal-400 dark:text-slate-500 transition-colors hover:text-coal-700 dark:hover:text-slate-200 dark:text-slate-300"
            >
              View source →
            </button>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-coal-100 pt-4">
        <span className="text-xs font-medium uppercase tracking-wide text-coal-400 dark:text-slate-500">
          Decide
        </span>
        {DECISIONS.map((d) => (
          <button
            key={d.key}
            type="button"
            disabled={busy}
            title={d.hint}
            onClick={() => void resolve(d.key)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              picked === d.key
                ? "border-coal-900 dark:border-slate-100 bg-coal-900 text-white dark:bg-slate-100 dark:text-slate-900"
                : "border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-coal-700 dark:text-slate-300 hover:border-coal-400 dark:hover:border-slate-600 hover:bg-coal-50 dark:hover:bg-slate-800"
            }`}
          >
            {d.label}
          </button>
        ))}
        {error && <span className="text-sm text-red-600 dark:text-red-400">{error}</span>}
      </div>
    </li>
  );
}

export default function ReviewPage() {
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("reviewer");
  const [comment, setComment] = useState("");
  const [sendingBackId, setSendingBackId] = useState<number | null>(null);
  const [busyReport, setBusyReport] = useState(false);
  const [activeCitation, setActiveCitation] = useState<EvidenceCitation | null>(null);
  const [recentlyResolved, setRecentlyResolved] = useState<
    { text: string; decision: string }[]
  >([]);

  const loadQueue = useCallback(async () => {
    try {
      setError(null);
      setQueue(await apiGet<ReviewQueue>("/api/v1/review/queue"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the review queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  async function decideReport(reportId: number, decision: "approve" | "send_back") {
    if (busyReport) return;
    setBusyReport(true);
    setError(null);
    setFeedback(null);
    try {
      await apiPost(`/api/v1/review/reports/${reportId}/decision`, {
        decision,
        comment,
      });
      setComment("");
      setFeedback(
        decision === "approve"
          ? `Report #${reportId} approved and finalized.`
          : `Report #${reportId} sent back for edits.`
      );
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed.");
    } finally {
      setBusyReport(false);
      setSendingBackId(null);
    }
  }

  const conflicts = queue?.conflicts ?? [];
  const reports = queue?.draft_reports ?? [];

  return (
    <>
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-coal-950 dark:text-slate-100">Review Queue</h1>
            <p className="mt-1 text-sm text-coal-500 dark:text-slate-400">
              Conflicts flagged by cross-source validation are never silently
              overwritten — resolve them here, then approve draft reports.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-sm text-coal-500 dark:text-slate-400">
              Reviewer
              <input
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                className="w-28 rounded-lg border border-coal-300 bg-white px-2 py-1 text-sm text-coal-900 outline-none focus:border-coal-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-slate-500"
              />
            </label>
            <button
              onClick={() => void loadQueue()}
              className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm font-medium text-coal-600 dark:text-slate-300 transition-colors hover:border-coal-400 dark:hover:border-slate-600 hover:text-coal-900 dark:hover:text-white dark:text-slate-100"
            >
              Refresh
            </button>
          </div>
        </header>

        {error && !loading && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400">
            {error}
          </div>
        )}
        {feedback && (
          <div className="mt-4 rounded-lg border border-source/20 bg-source-light px-3 py-2 text-sm text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300">
            {feedback}
          </div>
        )}

        <section className="mt-6">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-coal-950 dark:text-slate-100">
              Conflicts to resolve
            </h2>
            <span className="rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300">
              {conflicts.length}
            </span>
          </div>

          {loading ? (
            <div className="mt-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center text-sm text-coal-400 dark:text-slate-500 shadow-card">
              Loading review queue…
            </div>
          ) : conflicts.length === 0 ? (
            <div className="mt-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-card">
              <h3 className="text-sm font-semibold text-coal-800 dark:text-slate-200">
                No open conflicts
              </h3>
              <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                All extracted figures are consistent with the validated store.
              </p>
            </div>
          ) : (
            <ul className="mt-3 grid gap-4">
              {conflicts.map((conflict) => (
                <ConflictCard
                  key={conflict.id}
                  conflict={conflict}
                  reviewer={reviewer}
                  onResolved={(c, decision) => {
                    setQueue((prev) =>
                      prev
                        ? { ...prev, conflicts: prev.conflicts.filter((x) => x.id !== c.id) }
                        : prev
                    );
                    const kept = decision === "fact_a" ? "A" : decision === "fact_b" ? "B" : decision;
                    setRecentlyResolved((prev) => [
                      { text: `Conflict #${c.id} (${c.reason}) resolved → kept ${kept}`, decision },
                      ...prev,
                    ]);
                    setFeedback("Conflict resolved and recorded.");
                  }}
                  onCite={setActiveCitation}
                  error={error}
                  onError={setError}
                />
              ))}
            </ul>
          )}
        </section>

        {recentlyResolved.length > 0 && (
          <details className="mt-4 rounded-2xl border border-gap/20 bg-gap-light/50 p-4 dark:border-gap/30 dark:bg-gap/10">
            <summary className="cursor-pointer text-sm font-medium text-gap dark:text-amber-300">
              Resolved this session ({recentlyResolved.length})
            </summary>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-gap dark:text-amber-300">
              {recentlyResolved.map((r, i) => (
                <li key={i}>{r.text}</li>
              ))}
            </ul>
          </details>
        )}

        <section className="mt-10">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-coal-950 dark:text-slate-100">Draft reports</h2>
            <span className="rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-700 dark:text-slate-300">
              {reports.length}
            </span>
          </div>

          {loading ? null : reports.length === 0 ? (
            <div className="mt-3 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-card">
              <h3 className="text-sm font-semibold text-coal-800 dark:text-slate-200">
                No drafts awaiting review
              </h3>
              <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                Generate a report from the Reports tab to review it here.
              </p>
            </div>
          ) : (
            <ul className="mt-3 grid gap-3">
              {reports.map((report) => (
                <li
                  key={report.id}
                  className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-card"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-600 dark:text-slate-300">
                          {report.template_type}
                        </span>
                        <span className="text-xs text-coal-400 dark:text-slate-500">
                          Draft · {formatDate(report.generated_at)}
                        </span>
                      </div>
                      <h3 className="mt-1.5 font-medium text-coal-950 dark:text-slate-100">
                        {report.title}
                      </h3>
                      {report.summary ? (
                        <p className="mt-1 text-sm leading-relaxed text-coal-600 dark:text-slate-300">
                          {report.summary}
                        </p>
                      ) : (
                        <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                          No summary provided.
                        </p>
                      )}
                    </div>

                    <div className="flex flex-col items-end gap-2">
                      {sendingBackId === report.id ? (
                        <div className="flex flex-col gap-2 rounded-xl border border-coal-200 dark:border-slate-700 bg-coal-50/60 dark:bg-slate-800/60 p-3">
                          <textarea
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            placeholder="What needs fixing? (sent back as a review note)"
                            rows={2}
                            className="w-64 rounded-lg border border-coal-300 bg-white px-3 py-2 text-sm text-coal-900 outline-none focus:border-coal-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-slate-500"
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={busyReport}
                              onClick={() =>
                                void decideReport(report.id, "send_back")
                              }
                              className="rounded-lg bg-coal-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-coal-800 dark:hover:bg-white disabled:opacity-40"
                            >
                              Send back
                            </button>
                            <button
                              type="button"
                              disabled={busyReport}
                              onClick={() => setSendingBackId(null)}
                              className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm font-medium text-coal-600 dark:text-slate-300 hover:border-coal-400 dark:hover:border-slate-600"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={busyReport}
                            onClick={() => void decideReport(report.id, "approve")}
                            className="rounded-lg bg-coal-900 px-3.5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-coal-800 dark:hover:bg-white disabled:opacity-40"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={busyReport}
                            onClick={() => setSendingBackId(report.id)}
                            className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-1.5 text-sm font-medium text-coal-600 dark:text-slate-300 transition-colors hover:border-coal-400 dark:hover:border-slate-600 hover:text-coal-900 dark:hover:text-white dark:text-slate-100 disabled:opacity-40"
                          >
                            Send back
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <SourceEvidencePanel
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </>
  );
}