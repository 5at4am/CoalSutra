"use client";

import { useCallback, useEffect, useState } from "react";
import SourceChip, {
  type EvidenceCitation,
} from "@/components/SourceChip";
import SourceEvidencePanel from "@/components/SourceEvidencePanel";
import { apiGet, apiPost, API_BASE } from "@/lib/api";

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

const STATUS_BADGE: Record<ReportStatus, string> = {
  draft: "bg-coal-100 dark:bg-slate-800 text-coal-700 dark:text-slate-300 dark:bg-slate-800 dark:text-slate-300",
  reviewed:
    "bg-source-light text-source-dark dark:bg-source/20 dark:text-emerald-300",
  final: "bg-coal-900 text-white dark:bg-slate-100 dark:text-slate-900",
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

function ReportStatusBadge({ status }: { status: ReportStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_BADGE[status]}`}
    >
      {status}
    </span>
  );
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
  }

  function backToList() {
    setSelected(null);
    setError(null);
    setFeedback(null);
  }

  if (selected) {
    const sections = Object.entries(selected.content?.sections ?? {});
    return (
      <>
        <main className="mx-auto max-w-5xl px-4 pb-24 pt-6 sm:px-6">
          <button
            onClick={backToList}
            className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-coal-500 dark:text-slate-400 transition-colors hover:text-coal-900 dark:hover:text-white dark:text-slate-100"
          >
            ← All reports
          </button>

          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400">
              {error}
            </div>
          )}
          {feedback && (
            <div className="mb-4 rounded-lg border border-source/20 bg-source-light px-3 py-2 text-sm text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300">
              {feedback}
            </div>
          )}

          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <ReportStatusBadge status={selected.status} />
                <span className="rounded-full bg-coal-100 dark:bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-coal-600 dark:text-slate-300">
                  {selected.template_type}
                </span>
              </div>
              <h1 className="mt-2 text-xl font-semibold text-coal-950 dark:text-slate-100">
                {selected.title}
              </h1>
              <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                Generated {formatDate(selected.generated_at)} · Report #{selected.id}
              </p>
              {selected.review_note && (
                <p className="mt-2 max-w-2xl rounded-lg border border-gap/20 bg-gap-light px-3 py-2 text-sm text-gap dark:border-gap/30 dark:bg-gap/15 dark:text-amber-300">
                  <span className="font-medium">Review note: </span>
                  {selected.review_note}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={downloadPdf}
                className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2 text-sm font-medium text-coal-700 dark:text-slate-300 transition-colors hover:border-coal-400 dark:hover:border-slate-600 hover:bg-coal-50 dark:hover:bg-slate-800"
              >
                Download PDF
              </button>
              <button
                onClick={approve}
                disabled={approving || selected.status === "final"}
                className="rounded-lg bg-coal-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-coal-800 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
              >
                {approving
                  ? "Approving…"
                  : selected.status === "final"
                    ? "Final"
                    : selected.status === "reviewed"
                      ? "Approve & finalize"
                      : "Approve"}
              </button>
            </div>
          </header>

          <div className="mt-6 grid gap-4">
            {sections.map(([key, section]) => {
              const automatic = section.automatic === true;
              return (
                <section
                  key={key}
                  className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-card"
                >
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-coal-500 dark:text-slate-400">
                    {section.title}
                  </h2>
                  <p
                    className={`mt-3 whitespace-pre-wrap text-[15px] leading-relaxed text-coal-900 dark:text-slate-100 ${
                      automatic ? "font-mono text-sm text-coal-600 dark:text-slate-300" : ""
                    }`}
                  >
                    {section.body}
                  </p>
                  {!automatic && section.citations.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-coal-100 pt-3">
                      <span className="text-xs font-medium uppercase tracking-wide text-coal-400 dark:text-slate-500">
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
    <>
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-coal-950 dark:text-slate-100">Reports</h1>
            <p className="mt-1 text-sm text-coal-500 dark:text-slate-400">
              Auto-generated from validated, cited facts — approve drafts to
              finalize them.
            </p>
          </div>
          <button
            onClick={loadReports}
            className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm font-medium text-coal-600 dark:text-slate-300 transition-colors hover:border-coal-400 dark:hover:border-slate-600 hover:text-coal-900 dark:hover:text-white dark:text-slate-100"
          >
            Refresh
          </button>
        </header>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400">
            {error}
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[16rem_1fr]">
          {/* generate form */}
          <aside className="h-fit rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-card">
            <h2 className="text-sm font-semibold text-coal-900 dark:text-slate-100">
              Generate a new report
            </h2>
            <form
              className="mt-4 flex flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                void generate();
              }}
            >
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-coal-500 dark:text-slate-400">
                  Template
                </span>
                <select
                  value={templateType}
                  onChange={(e) => setTemplateType(e.target.value)}
                  className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-coal-900 dark:text-slate-100 outline-none focus:border-coal-500 dark:focus:border-slate-500"
                >
                  {templates.map((t) => (
                    <option key={t.template_type} value={t.template_type}>
                      {t.title}
                    </option>
                  ))}
                </select>
                <span className="text-xs leading-relaxed text-coal-400 dark:text-slate-500">
                  {templates.find((t) => t.template_type === templateType)?.description}
                </span>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-coal-500 dark:text-slate-400">
                  From
                </span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-coal-900 dark:text-slate-100 outline-none focus:border-coal-500 dark:focus:border-slate-500"
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-coal-500 dark:text-slate-400">
                  To
                </span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="rounded-lg border border-coal-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-coal-900 dark:text-slate-100 outline-none focus:border-coal-500 dark:focus:border-slate-500"
                />
              </label>

              <button
                type="submit"
                disabled={generating}
                className="rounded-lg bg-coal-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-coal-800 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
              >
                {generating ? "Drafting…" : "Generate draft"}
              </button>
            </form>
          </aside>

          {/* list */}
          <div>
            {reports === null ? (
              <div className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center text-sm text-coal-400 dark:text-slate-500 shadow-card">
                Loading reports…
              </div>
            ) : reports.length === 0 ? (
              <div className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-card">
                <h3 className="text-sm font-semibold text-coal-800 dark:text-slate-200">
                  No reports yet
                </h3>
                <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">
                  Generate a draft from a template on the left — every figure
                  will cite its source document and page.
                </p>
              </div>
            ) : (
              <ul className="grid gap-3">
                {reports.map((report) => (
                  <li key={report.id}>
                    <button
                      onClick={() => openReport(report)}
                      className="flex w-full items-center justify-between gap-4 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 text-left shadow-card transition-colors hover:border-coal-300 dark:hover:border-slate-600 dark:border-slate-700 hover:bg-coal-50 dark:hover:bg-slate-800"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-coal-950 dark:text-slate-100">
                          {report.title}
                        </p>
                        <p className="mt-0.5 text-sm text-coal-400 dark:text-slate-500">
                          {report.template_type} ·{" "}
                          {formatDate(report.generated_at)}
                        </p>
                      </div>
                      <ReportStatusBadge status={report.status} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </main>
    </>
  );
}