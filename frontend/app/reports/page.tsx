"use client";

import { useCallback, useEffect, useState } from "react";
import SourceChip, {
  type EvidenceCitation,
} from "@/components/SourceChip";
import SourceEvidencePanel from "@/components/SourceEvidencePanel";
import { apiGet, apiPost, API_BASE } from "@/lib/api";
import Icon from "@/components/Icon";
import PageHeader, { SectionHeader } from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import AlertBanner from "@/components/AlertBanner";
import EmptyState from "@/components/EmptyState";
import { btnPrimary, btnSecondary, inputBase, cardBase } from "@/lib/ui";

type ReportStatus = "draft" | "reviewed" | "final";

type ReportSection = {
  title: string;
  body: string;
  citations: EvidenceCitation[];
  automatic?: boolean;
};

type Report = {
  id: number;
  title: string;
  template_type: string;
  generated_at: string;
  status: ReportStatus;
  content: { sections: Record<string, ReportSection> };
  export_path: string | null;
  review_note: string | null;
};

type ReportTemplate = {
  template_type: string;
  title: string;
  description: string;
  sections: string[];
};

type LintIssue = {
  severity: "error" | "warning" | "info";
  section: string;
  number: string;
  context: string;
  reason: string;
};

type LintResult = {
  ok: boolean;
  summary: {
    figures_checked: number;
    figures_matched_to_facts: number;
    errors: number;
    warnings: number;
    infos: number;
  };
  issues: LintIssue[];
};

const FALLBACK_TEMPLATES: ReportTemplate[] = [
  {
    template_type: "production_summary",
    title: "Production Summary",
    description: "Coal production, overburden removal and dispatch figures.",
    sections: ["overview", "key_figures", "trends", "sources"],
  },
  {
    template_type: "coal_quality_report",
    title: "Coal Quality Report",
    description: "Quality parameters: ash, moisture, sulphur, grade / GCV.",
    sections: ["overview", "key_figures", "grade_analysis", "sources"],
  },
  {
    template_type: "reserve_estimate",
    title: "Reserve Estimate",
    description: "Coal reserve estimates per block / seam.",
    sections: ["overview", "reserve_breakdown", "trends", "sources"],
  },
];

const STATUS_TONE: Record<ReportStatus, "neutral" | "info" | "success"> = {
  draft: "neutral",
  reviewed: "info",
  final: "success",
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

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[] | null>(null);
  const [templates, setTemplates] = useState<ReportTemplate[]>(FALLBACK_TEMPLATES);
  const [selected, setSelected] = useState<Report | null>(null);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<EvidenceCitation | null>(null);
  const [lint, setLint] = useState<LintResult | null>(null);
  const [linting, setLinting] = useState(false);

  // generate form state
  const [templateType, setTemplateType] = useState("production_summary");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadReports = useCallback(async () => {
    try {
      setError(null);
      setReports(await apiGet<Report[]>("/api/v1/reports"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    }
  }, []);

  useEffect(() => {
    void loadReports();
    apiGet<ReportTemplate[]>("/api/v1/reports/templates")
      .then(setTemplates)
      .catch(() => {
        /* FALLBACK_TEMPLATES stands in offline */
      });
  }, [loadReports]);

  async function generate() {
    const filters: Record<string, string> = {};
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;

    setGenerating(true);
    setError(null);
    setFeedback(null);
    try {
      const report = await apiPost<Report>("/api/v1/reports/generate", {
        template_type: templateType,
        filters,
      });
      setReports((prev) =>
        prev ? [report, ...prev.filter((r) => r.id !== report.id)] : [report]
      );
      setSelected(report);
      setFeedback("Report generated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function approve() {
    if (!selected || selected.status === "final") return;
    setApproving(true);
    setError(null);
    setFeedback(null);
    try {
      const updated = await apiPost<Report>(`/api/v1/reports/${selected.id}/approve`);
      setSelected(updated);
      setReports((prev) =>
        prev ? prev.map((r) => (r.id === updated.id ? updated : r)) : prev
      );
      setFeedback("Approved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setApproving(false);
    }
  }

  async function runLint() {
    if (!selected) return;
    setLinting(true);
    setLint(null);
    setError(null);
    try {
      setLint(await apiGet<LintResult>(`/api/v1/reports/${selected.id}/lint`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Facts check failed.");
    } finally {
      setLinting(false);
    }
  }

  async function downloadPdf() {
    if (!selected) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${selected.id}/export`);
      if (!res.ok) {
        throw new Error(`Download failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${selected.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    }
  }

  function openReport(report: Report) {
    setSelected(report);
    setError(null);
    setFeedback(null);
    setLint(null);
  }

  function backToList() {
    setSelected(null);
    setError(null);
    setFeedback(null);
    setLint(null);
  }

  if (selected) {
    const sections = Object.entries(selected.content?.sections ?? {});
    return (
      <>
        <main className="mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6">
          <button
            onClick={backToList}
            className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink dark:text-slate-400 dark:hover:text-white"
          >
            <Icon name="arrow-left" size={14} />
            All reports
          </button>

          {error && (
            <div className="mb-4">
              <AlertBanner tone="error">{error}</AlertBanner>
            </div>
          )}
          {feedback && (
            <div className="mb-4">
              <AlertBanner tone="success">{feedback}</AlertBanner>
            </div>
          )}

          <header className={`${cardBase} overflow-hidden`}>
            <div className="border-b border-coal-100 p-6 dark:border-slate-800">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge tone={STATUS_TONE[selected.status]} label={selected.status} dot />
                    <span className="rounded-full bg-coal-100 px-2.5 py-0.5 font-mono text-[11px] font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-400">
                      {selected.template_type}
                    </span>
                  </div>
                  <h1 className="mt-3 text-xl font-semibold tracking-tight text-ink dark:text-slate-100">
                    {selected.title}
                  </h1>
                  <p className="mt-1 text-sm text-ink-muted dark:text-slate-500">
                    Generated {formatDate(selected.generated_at)} · Report #{selected.id}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <button onClick={() => void runLint()} disabled={linting} className={`${btnSecondary} px-3 py-2`}>
                    <Icon name="search" size={15} />
                    {linting ? "Checking…" : "Check facts"}
                  </button>
                  <button onClick={() => void downloadPdf()} className={`${btnSecondary} px-3 py-2`}>
                    <Icon name="download" size={15} />
                    Download PDF
                  </button>
                  <button
                    onClick={() => void approve()}
                    disabled={approving || selected.status === "final"}
                    className={`${btnPrimary} px-4 py-2`}
                  >
                    <Icon name="check" size={15} />
                    {approving
                      ? "Approving…"
                      : selected.status === "final"
                        ? "Final"
                        : selected.status === "reviewed"
                          ? "Approve & finalize"
                          : "Approve"}
                  </button>
                </div>
              </div>

              {selected.review_note && (
                <div className="mt-4">
                  <AlertBanner tone="warning">
                    <span className="font-medium">Review note: </span>
                    {selected.review_note}
                  </AlertBanner>
                </div>
              )}

              {lint && (
                <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
                  lint.ok
                    ? "border-source/25 bg-source-light text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300"
                    : "border-red-200 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
                }`}>
                  <p className="flex items-center gap-2 font-medium">
                    {lint.ok ? (
                      <Icon name="check-circle" size={15} />
                    ) : (
                      <Icon name="alert" size={15} />
                    )}
                    {lint.ok
                      ? "Facts check passed — every figure is backed by a cited fact."
                      : `Facts check flagged ${lint.summary.errors} unsupported figure${lint.summary.errors === 1 ? "" : "s"}.`}
                  </p>
                  <p className="mt-1 text-xs opacity-80">
                    {lint.summary.figures_checked} figures checked ·{" "}
                    {lint.summary.figures_matched_to_facts} matched to facts ·{" "}
                    {lint.summary.errors} errors · {lint.summary.infos} infos
                  </p>
                </div>
              )}

              {lint && lint.issues.length > 0 && (
                <ul className="mt-4 grid gap-2">
                  {lint.issues.map((issue, i) => (
                    <li
                      key={i}
                      className={`rounded-lg border px-3 py-2 ${
                        issue.severity === "error"
                          ? "border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10"
                          : "border-coal-200 bg-canvas dark:border-slate-700 dark:bg-slate-800"
                      }`}
                    >
                      <p className={`text-xs font-semibold ${issue.severity === "error" ? "text-red-700 dark:text-red-400" : "text-ink dark:text-slate-200"}`}>
                        {issue.severity === "error" ? "Error" : "Info"} · {issue.section} ·{" "}
                        <code className="font-mono">{issue.number}</code>
                      </p>
                      <p className={`mt-0.5 text-xs leading-relaxed ${issue.severity === "error" ? "text-red-600 dark:text-red-300/90" : "text-ink-muted dark:text-slate-400"}`}>
                        {issue.reason}
                      </p>
                      <p className="mt-1 truncate font-mono text-[11px] text-ink-muted/80 dark:text-slate-500">
                        …{issue.context}…
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </header>

          <div className="mt-6 grid gap-4">
            {sections.map(([key, section]) => {
              const automatic = section.automatic === true;
              return (
                <section key={key} className={`${cardBase} p-5`}>
                  <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-muted dark:text-slate-400">
                    {automatic && (
                      <Icon name="spark" size={13} className="text-coal-400 dark:text-slate-500" />
                    )}
                    {section.title}
                  </h2>
                  <p
                    className={`mt-3 whitespace-pre-wrap text-[15px] leading-relaxed ${
                      automatic
                        ? "font-mono text-sm text-ink-muted dark:text-slate-300"
                        : "text-ink dark:text-slate-100"
                    }`}
                  >
                    {section.body}
                  </p>
                  {!automatic && section.citations.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-coal-100 pt-3 dark:border-slate-800">
                      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                        <Icon name="source" size={12} />
                        Sources
                      </span>
                      {section.citations.map((citation, i) => (
                        <SourceChip
                          key={i}
                          citation={citation}
                          onClick={() => setActiveCitation(citation)}
                        />
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        </main>

        <SourceEvidencePanel
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
        />
      </>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">
      <PageHeader
        title="Reports"
        purpose="Auto-generated from validated, cited facts — review and approve drafts to finalize them."
        actions={
          <button onClick={() => void loadReports()} className={`${btnSecondary} px-3 py-2`}>
            <Icon name="refresh" size={15} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="mt-4">
          <AlertBanner tone="error">{error}</AlertBanner>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[18rem_1fr]">
        {/* ---------- generate form ---------- */}
        <aside className={`${cardBase} h-fit p-5 lg:sticky lg:top-8`}>
          <SectionHeader title="Generate a new report" icon="report" />
          <form
            className="mt-4 flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void generate();
            }}
          >
            <fieldset>
              <legend className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-400">
                Template
              </legend>
              <div className="mt-2 grid gap-2" role="radiogroup" aria-label="Report template">
                {templates.map((t) => {
                  const activeTpl = templateType === t.template_type;
                  return (
                    <label
                      key={t.template_type}
                      className={`flex cursor-pointer gap-2.5 rounded-xl border p-3 transition-colors ${
                        activeTpl
                          ? "border-accent-ring/70 bg-accent-faint dark:border-accent/60 dark:bg-accent/10"
                          : "border-coal-200 hover:border-coal-300 dark:border-slate-700 dark:hover:border-slate-600"
                      }`}
                    >
                      <input
                        type="radio"
                        name="template"
                        value={t.template_type}
                        checked={activeTpl}
                        onChange={(e) => setTemplateType(e.target.value)}
                        className="mt-0.5 h-4 w-4 accent-accent"
                      />
                      <span className="min-w-0">
                        <span className={`block text-sm font-medium ${activeTpl ? "text-accent-strong dark:text-amber-300" : "text-ink dark:text-slate-100"}`}>
                          {t.title}
                        </span>
                        <span className="mt-0.5 block text-xs leading-relaxed text-ink-muted dark:text-slate-400">
                          {t.description}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <div className="flex gap-3">
              <label className="flex flex-1 flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-400">
                  From
                </span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className={inputBase}
                />
              </label>
              <label className="flex flex-1 flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-400">
                  To
                </span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className={inputBase}
                />
              </label>
            </div>

            <button type="submit" disabled={generating} className={btnPrimary}>
              <Icon name="spark" size={15} />
              {generating ? "Drafting…" : "Generate draft"}
            </button>
          </form>
        </aside>

        {/* ---------- list ---------- */}
        <div>
          {reports === null ? (
            <div className="flex items-center justify-center gap-2 rounded-2xl border border-coal-200 bg-white p-10 text-sm text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
              <Icon name="refresh" size={14} className="animate-spin" />
              Loading reports…
            </div>
          ) : reports.length === 0 ? (
            <EmptyState
              icon="report"
              title="No reports yet"
              body="Generate a draft from a template on the left — every figure will cite its source document and page."
            />
          ) : (
            <ul className="grid gap-3">
              {reports.map((report) => (
                <li key={report.id}>
                  <button
                    onClick={() => openReport(report)}
                    className={`${cardBase} group flex w-full items-center justify-between gap-4 p-4 text-left transition-colors hover:border-coal-300 hover:shadow-pop dark:hover:border-slate-600 dark:hover:bg-slate-800`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-coal-100 text-coal-500 sm:inline-flex dark:bg-slate-800 dark:text-slate-400">
                        <Icon name="report" size={16} />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink dark:text-slate-100">
                          {report.title}
                        </span>
                        <span className="mt-0.5 block text-sm text-ink-muted dark:text-slate-500">
                          {report.template_type} · {formatDate(report.generated_at)}
                        </span>
                      </span>
                    </div>
                    <span className="flex shrink-0 items-center gap-3">
                      <StatusBadge tone={STATUS_TONE[report.status]} label={report.status} dot />
                      <Icon
                        name="chevron-right"
                        size={15}
                        className="text-coal-300 transition-transform group-hover:translate-x-0.5 dark:text-slate-600"
                      />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}