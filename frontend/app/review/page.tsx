"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import type { EvidenceCitation } from "@/components/SourceChip";
import SourceEvidencePanel from "@/components/SourceEvidencePanel";
import { apiGet, apiPost } from "@/lib/api";
import Icon from "@/components/Icon";
import PageHeader, { SectionHeader } from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import AlertBanner from "@/components/AlertBanner";
import EmptyState from "@/components/EmptyState";
import { btnPrimary, btnSecondary, inputBase, cardBase } from "@/lib/ui";
import imgReview from "@/app/public/img-3D.png";

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

function ConfidenceBadge({ confidence }: { confidence: number }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        confidence >= 0.9
          ? "bg-source-light text-source-dark dark:bg-source/20 dark:text-emerald-300"
          : confidence >= 0.7
            ? "bg-gap-light text-gap dark:bg-gap/15 dark:text-amber-300"
            : "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400"
      }`}
    >
      <Icon name="shield" size={10} />
      {Math.round(confidence * 100)}% conf
    </span>
  );
}

function FactPanel({ fact, side }: { fact: FactItem; side: "A" | "B" }) {
  return (
    <figure
      className={`flex-1 overflow-hidden rounded-xl border bg-white/70 dark:bg-slate-800/60 ${
        side === "A"
          ? "border-coal-200 dark:border-slate-700"
          : "border-coal-200 dark:border-slate-700"
      }`}
    >
      <span
        aria-hidden="true"
        className={`block h-1 ${side === "A" ? "bg-info" : "bg-source"}`}
      />
      <div className="p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted dark:text-slate-500">
            <span
              className={`inline-flex h-4 w-4 items-center justify-center rounded text-[10px] font-bold text-white ${
                side === "A" ? "bg-info" : "bg-source"
              }`}
            >
              {side}
            </span>
            Fact {side}
          </span>
          <ConfidenceBadge confidence={fact.confidence} />
        </div>
        <p className="mt-2.5 text-2xl font-semibold tracking-tight text-ink dark:text-slate-100">
          {fact.value}
          {fact.unit ? (
            <span className="ml-1 align-middle text-sm font-medium text-ink-muted dark:text-slate-500">
              {fact.unit}
            </span>
          ) : null}
        </p>
        <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
          {fact.entity}
          {fact.date_reference ? ` · ${String(fact.date_reference).slice(0, 4)}` : ""}
        </p>
        <blockquote className="mt-3 border-l-2 border-coal-200 pl-3 text-sm leading-relaxed text-ink-muted dark:border-slate-600 dark:text-slate-300">
          &ldquo;{fact.snippet}&rdquo;
        </blockquote>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-coal-200 bg-white px-2.5 py-0.5 text-xs font-medium text-ink-muted dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300">
            <Icon name="file" size={11} className="shrink-0 opacity-70" />
            <span className="max-w-[12rem] truncate">{fact.document_name}</span>
          </span>
          {fact.page_number !== null && (
            <span className="rounded-full border border-coal-200 bg-white px-2.5 py-0.5 font-mono text-xs font-medium text-ink-muted dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300">
              p.{fact.page_number}
            </span>
          )}
        </div>
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
    <li className={`${cardBase} p-5`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink dark:text-slate-100">
          <Icon name="alert" size={15} className="text-gap dark:text-amber-400" />
          {conflict.reason}
        </h3>
        <StatusBadge tone="danger" label="open" dot />
      </div>
      <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
        Conflict #{conflict.id} · raised by cross-source validation · the two
        extractions disagree on the same fact.
      </p>

      <div className="mt-4 flex flex-col gap-4 md:flex-row">
        {[conflict.fact_a, conflict.fact_b].map((fact, i) => {
          const side = i === 0 ? "A" : "B";
          const citation: EvidenceCitation = {
            document_name: fact.document_name,
            page_number: fact.page_number ?? 0,
            snippet: fact.snippet,
          };
          return (
            <div key={fact.fact_id} className="flex flex-1 flex-col gap-1.5">
              <FactPanel fact={fact} side={side} />
              <button
                type="button"
                onClick={() => onCite(citation)}
                className="inline-flex items-center gap-1 self-end text-xs font-medium text-ink-muted transition-colors hover:text-ink dark:text-slate-300 dark:hover:text-white"
              >
                <Icon name="source" size={12} />
                View source
                <Icon name="chevron-right" size={12} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-coal-100 pt-4 dark:border-slate-800">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
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
                ? "border-accent bg-accent text-white dark:border-accent dark:bg-accent dark:text-white"
                : "border-coal-300 bg-white text-ink-muted hover:border-coal-400 hover:bg-canvas hover:text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:hover:text-white"
            }`}
          >
            {picked === d.key ? (
              <>
                <Icon name="check" size={13} className="mr-1 inline align-[-2px]" />
                {d.label}
              </>
            ) : (
              d.label
            )}
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
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6">
        <PageHeader
          title="Review Queue"
          purpose="Conflicts flagged by cross-source validation are never silently overwritten — resolve them here, then approve draft reports."
          actions={
            <>
              <label className="flex items-center gap-2 text-sm text-ink-muted dark:text-slate-400">
                <span className="hidden sm:inline">Reviewer</span>
                <input
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  placeholder="your name"
                  className={`${inputBase} w-32`}
                />
              </label>
              <button onClick={() => void loadQueue()} className={`${btnSecondary} px-3 py-2`}>
                <Icon name="refresh" size={15} />
                Refresh
              </button>
            </>
          }
        />

        {error && !loading && (
          <div className="mt-4">
            <AlertBanner tone="error">{error}</AlertBanner>
          </div>
        )}
        {feedback && (
          <div className="mt-4">
            <AlertBanner tone="success">{feedback}</AlertBanner>
          </div>
        )}

        {/* ---------- how the review gate works ---------- */}
        <section className="mt-6 grid items-center gap-6 rounded-2xl border border-coal-200 bg-white p-5 shadow-card dark:border-slate-700 dark:bg-slate-900 lg:grid-cols-[5fr_6fr] lg:gap-8">
          <div>
            <SectionHeader title="How the review gate works" icon="shield" />
            <ul className="mt-4 grid gap-2.5">
              {[
                "Conflicts are raised when the same fact is extracted with different values from two sources.",
                "Both extractions are shown side by side with their snippets, pages and confidence scores.",
                "A named reviewer decides — keep one side, keep both, or reject both; nothing is guessed.",
                "Resolved facts and approved drafts flow into the validated store, now recorded with who decided.",
              ].map((point) => (
                <li
                  key={point}
                  className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-muted dark:text-slate-300"
                >
                  <Icon name="check" size={14} className="mt-0.5 shrink-0 text-source dark:text-emerald-400" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <Image
            src={imgReview}
            alt="Human review illustration: two conflicting source facts compared side by side, an expert decision recorded, and approved facts finalised."
            className="w-full rounded-xl border border-coal-200 bg-canvas dark:border-slate-700 dark:bg-slate-800"
            sizes="(min-width: 1024px) 50vw, 100vw"
          />
        </section>

        <section className="mt-8">
          <SectionHeader
            title="Conflicts to resolve"
            icon="alert"
            meta={
              <span className="rounded-full bg-coal-100 px-2.5 py-0.5 text-xs font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-400">
                {conflicts.length}
              </span>
            }
          />

          {loading ? (
            <div className="mt-3 flex items-center justify-center gap-2 rounded-2xl border border-coal-200 bg-white p-10 text-sm text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
              <Icon name="refresh" size={14} className="animate-spin" />
              Loading review queue…
            </div>
          ) : conflicts.length === 0 ? (
            <div className="mt-3">
              <EmptyState
                icon="shield"
                title="No open conflicts"
                body="All extracted figures are consistent with the validated store."
              />
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
            <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-gap dark:text-amber-300">
              <Icon name="check-circle" size={14} />
              Resolved this session ({recentlyResolved.length})
            </summary>
            <ul className="mt-2 grid gap-1.5">
              {recentlyResolved.map((r, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-gap dark:text-amber-300">
                  <Icon name="check" size={12} />
                  {r.text}
                </li>
              ))}
            </ul>
          </details>
        )}

        <section className="mt-10">
          <SectionHeader
            title="Draft reports"
            icon="report"
            meta={
              <span className="rounded-full bg-coal-100 px-2.5 py-0.5 text-xs font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-400">
                {reports.length}
              </span>
            }
          />

          {loading ? null : reports.length === 0 ? (
            <div className="mt-3">
              <EmptyState
                icon="report"
                title="No drafts awaiting review"
                body="Generate a report from the Reports tab to review it here."
              />
            </div>
          ) : (
            <ul className="mt-3 grid gap-3">
              {reports.map((report) => (
                <li key={report.id} className={`${cardBase} p-4`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-coal-100 px-2.5 py-0.5 font-mono text-[11px] font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-400">
                          {report.template_type}
                        </span>
                        <StatusBadge tone="neutral" label="draft" dot />
                        <span className="text-xs text-ink-muted dark:text-slate-500">
                          {formatDate(report.generated_at)}
                        </span>
                      </div>
                      <h3 className="mt-1.5 font-medium text-ink dark:text-slate-100">
                        {report.title}
                      </h3>
                      {report.summary ? (
                        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted dark:text-slate-300">
                          {report.summary}
                        </p>
                      ) : (
                        <p className="mt-1 text-sm text-ink-muted/70 dark:text-slate-500">
                          No summary provided.
                        </p>
                      )}
                    </div>

                    <div className="flex flex-col items-end gap-2">
                      {sendingBackId === report.id ? (
                        <div className="flex flex-col gap-2 rounded-xl border border-coal-200 bg-canvas p-3 dark:border-slate-700 dark:bg-slate-800">
                          <textarea
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            placeholder="What needs fixing? (sent back as a review note)"
                            rows={2}
                            className={`${inputBase} w-72`}
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={busyReport}
                              onClick={() => void decideReport(report.id, "send_back")}
                              className={btnPrimary}
                            >
                              Send back
                            </button>
                            <button
                              type="button"
                              disabled={busyReport}
                              onClick={() => setSendingBackId(null)}
                              className={btnSecondary}
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
                            className={btnPrimary}
                          >
                            <Icon name="check" size={14} />
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={busyReport}
                            onClick={() => setSendingBackId(report.id)}
                            className={btnSecondary}
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