"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";

type Metrics = {
  documents_total: number;
  documents_processed: number;
  open_conflicts: number;
  flagged_documents_pct: number;
  avg_query_ms: number;
  queries_served: number;
};

type DocumentItem = {
  id: number;
  filename: string;
  source_type: string;
  status: string;
  fact_count: number;
};

const MODULES = [
  {
    href: "/ingest",
icon: "↑",
    title: "Ingest",
    accent: "text-coal-700",
    description:
      "Upload scanned & born-digital PDFs, images, or spreadsheets. The pipeline classifies each file and routes it to the right extractor automatically.",
    points: ["Scanned vs digital routing", "OCR-scalable providers", "Upload in bulk"],
    cta: "Upload documents",
  },
  {
    href: "/chat",
    icon: "Q",
    title: "Ask the corpus",
    accent: "text-coal-700",
    description:
      "Ground-RAG answers over the validated store — every claim is answered only from retrieved chunks and cites its source document and page.",
    points: ["Cited answers, no hallucination", "Honest no-evidence state", "Source viewer panel"],
    cta: "Ask a question",
  },
  {
    href: "/reports",
icon: "∑",
    title: "Auto reports",
    accent: "text-coal-700",
    description:
      "Generate structured reports from validated facts with template-driven sections, then export them straight to PDF.",
    points: ["3 report templates", "Every figure cited", "PDF export built in"],
    cta: "Draft a report",
  },
  {
    href: "/dashboard",
icon: "◉",
    title: "Word cloud & topics",
    accent: "text-coal-700",
    description:
      "See the corpus at a glance — terms, topic clusters and document health without reading every file.",
    points: ["Live word cloud", "Topic clustering", "Document status metrics"],
    cta: "Open dashboard",
  },
  {
    href: "/review",
icon: "√",
    title: "Review queue",
    accent: "text-coal-700",
    description:
      "Cross-source conflicts are flagged, never silently overwritten. Decide which fact stands — or keep both with a note.",
    points: ["Conflict detection", "Keep A / B / both / neither", "Report approval gate"],
    cta: "Review conflicts",
  },
];

const PIPELINE = [
  { step: "1", title: "Ingest", text: "Files land in the system; routing decides scanned vs digital." },
  { step: "2", title: "Extract", text: "Text, tables and numbers become one normalized schema." },
  { step: "3", title: "Validate", text: "Cross-source checks flag value conflicts for a human." },
  { step: "4", title: "Store", text: "Facts in Postgres, embeddings in the vector store." },
  { step: "5", title: "Serve", text: "Query (cited), reports, topics — all from the same store." },
];

export default function LandingPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [docs, setDocs] = useState<DocumentItem[] | null>(null);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [question, setQuestion] = useState("");

  const load = useCallback(async () => {
    try {
      const [m, d] = await Promise.all([
        apiGet<Metrics>("/api/v1/metrics/summary"),
        apiGet<DocumentItem[]>("/api/v1/documents"),
      ]);
      setMetrics(m);
      setDocs(d);
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totalFacts =
    docs?.filter((d) => d.status === "processed").reduce((n, d) => n + d.fact_count, 0) ?? 0;

  const stats = metrics
    ? [
        { label: "Documents ingested", value: String(metrics.documents_total) },
        { label: "Facts extracted", value: String(totalFacts) },
        {
          label: "Open conflicts",
          value: String(metrics.open_conflicts),
          warn: metrics.open_conflicts > 0,
        },
        { label: "Flagged docs", value: `${Math.round(metrics.flagged_documents_pct)}%` },
        { label: "Avg query time", value: metrics.avg_query_ms == null ? "—" : `${Math.round(metrics.avg_query_ms)} ms` },
        { label: "Queries answered", value: String(metrics.queries_served) },
      ]
    : [];

  function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    router.push(`/chat?q=${encodeURIComponent(q)}`);
  }

return (
    <>
      <main className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        {/* ---------- hero ---------- */}
        <section className="mt-10 overflow-hidden rounded-3xl bg-coal-950 px-6 py-14 text-white sm:px-12 sm:py-16">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium tracking-wide text-coal-200">
              <span className="h-1.5 w-1.5 rounded-full bg-source" />
              Smart India Hackathon 2026 · Ministry of Coal / Coal India Ltd.
            </p>
            <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
              From scattered mining documents
              <span className="block text-coal-300">to traceable, queryable data.</span>
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-coal-300">
              CMPDI and its subsidiaries sit on decades of geological reports,
              scanned PDFs, maps and spreadsheets. This platform ingests them,
              extracts structured facts, flags conflicts instead of guessing, and
              powers cited answers, auto-generated reports and corpus-wide topic
              analysis.
            </p>

            <form
              onSubmit={ask}
              className="mt-8 flex max-w-xl items-center gap-2 rounded-2xl border border-white/15 bg-white p-2 shadow-card transition-colors focus-within:border-source"
            >
              <span className="pl-3 text-sm text-coal-400">Ask</span>
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="What is the coal reserve of Jharia as of 2019?"
                className="flex-1 bg-transparent px-2 py-2 text-[15px] text-coal-950 outline-none placeholder:text-coal-400"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-coal-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-coal-800"
              >
                Ask
              </button>
            </form>

            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href="/ingest"
                className="rounded-xl bg-source px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-source-dark"
              >
                Ingest documents
              </a>
              <a
                href="/chat"
                className="rounded-xl border border-white/20 bg-white/5 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/10"
              >
                Explore the corpus
              </a>
            </div>
          </div>
        </section>

        {/* ---------- live stats band ---------- */}
        <section className="mt-10">
          {backendUp === null ? null : backendUp ? (
            <>
              <div className="mb-4 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-source" />
<h2 className="text-sm font-semibold uppercase tracking-wide text-coal-500 dark:text-slate-400">
                  Live corpus status
                </h2>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {stats.map((stat) => (
                  <div
                    key={stat.label}
className={`rounded-2xl border bg-white p-4 shadow-card dark:bg-slate-900 ${
                      stat.warn ? "border-gap/30" : "border-coal-200 dark:border-slate-700"
                    }`}
                  >
                    <p
                      className={`text-2xl font-bold tracking-tight ${
                        stat.warn ? "text-gap dark:text-amber-300" : "text-coal-950 dark:text-slate-100"
                      }`}
                    >
                      {stat.value}
                    </p>
                    <p className="mt-1 text-xs font-medium uppercase tracking-wide text-coal-400 dark:text-slate-500">
                      {stat.label}
                    </p>
                  </div>
                ))}
              </div>
              {docs && docs.length > 0 && (
<div className="mt-4 rounded-2xl border border-coal-200 bg-white p-4 shadow-card dark:border-slate-700 dark:bg-slate-900">
                  <p className="text-xs font-medium uppercase tracking-wide text-coal-400 dark:text-slate-500">
                    Recently ingested
                  </p>
                  <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                    {docs.slice(0, 4).map((doc) => (
                      <li
                        key={doc.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-coal-100 px-3 py-2 text-sm dark:border-slate-800"
                      >
                        <span className="truncate text-coal-800 dark:text-slate-200">{doc.filename}</span>
                        <span className="shrink-0 text-xs text-coal-400 dark:text-slate-500">
                          {doc.fact_count} fact{doc.fact_count === 1 ? "" : "s"} ·{" "}
                          {doc.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-gap/30 bg-gap-light px-4 py-3 text-sm text-gap dark:border-gap/40 dark:bg-gap/15 dark:text-amber-300">
              Backend is offline right now — start it with{" "}
              <code className="rounded bg-white/60 px-1.5 py-0.5 font-mono text-xs dark:bg-white/10">
                uvicorn app.main:app --reload
              </code>{" "}
              from <code className="rounded bg-white/60 px-1.5 py-0.5 font-mono text-xs dark:bg-white/10">backend/</code>. The
              modules below are always ready to explore.
            </div>
          )}
        </section>

        {/* ---------- pipeline ---------- */}
        <section className="mt-14">
<h2 className="text-2xl font-bold tracking-tight text-coal-950 dark:text-slate-100">How it works</h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-coal-500 dark:text-slate-400">
            One backbone shared by every screen: ingest → extract → validate →
            store → serve. Nothing is guesswork — numbers carry their source.
          </p>
          <ol className="mt-6 grid gap-3 md:grid-cols-5">
            {PIPELINE.map((p, i) => (
              <li
                key={p.step}
className="relative rounded-2xl border border-coal-200 bg-white p-4 shadow-card dark:border-slate-700 dark:bg-slate-900"
              >
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-coal-900 text-sm font-bold text-white dark:bg-slate-100 dark:text-slate-900">
                  {p.step}
                </span>
                <h3 className="mt-3 text-sm font-semibold text-coal-950 dark:text-slate-100">{p.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-coal-500 dark:text-slate-400">{p.text}</p>
                {i < PIPELINE.length - 1 && (
                  <span className="absolute -right-2.5 top-1/2 hidden -translate-y-1/2 text-coal-300 md:inline dark:text-slate-600">
                    →
                  </span>
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* ---------- modules ---------- */}
        <section className="mt-14">
<h2 className="text-2xl font-bold tracking-tight text-coal-950 dark:text-slate-100">
            What you can do
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-coal-500 dark:text-slate-400">
            Five tools over the same validated store — each one demonstrates a
            mandated SIH deliverable.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((m) => (
              <a
                key={m.title}
                href={m.href}
className="group flex flex-col rounded-2xl border border-coal-200 bg-white p-5 shadow-card transition-colors hover:border-coal-400 hover:bg-coal-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 dark:hover:bg-slate-800"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-lg font-bold text-coal-700 dark:bg-slate-800 dark:text-slate-300">
                  {m.icon}
                </div>
                <h3 className="mt-3 text-base font-semibold text-coal-950 dark:text-slate-100">
                  {m.title}
                </h3>
                <p className="mt-1 flex-1 text-sm leading-relaxed text-coal-500 dark:text-slate-400">
                  {m.description}
                </p>
                <ul className="mt-3 grid gap-1">
                  {m.points.map((point) => (
                    <li
                      key={point}
                      className="flex items-center gap-2 text-xs text-coal-600 dark:text-slate-300"
                    >
                      <span className="text-source">✓</span>
                      {point}
                    </li>
                  ))}
                </ul>
                <span className="mt-4 text-sm font-medium text-coal-700 transition-colors group-hover:text-coal-950 dark:text-slate-300 dark:group-hover:text-white">
                  {m.cta} →
                </span>
              </a>
            ))}
          </div>
        </section>

        {/* ---------- traceability promise ---------- */}
<section className="mt-14 rounded-3xl border border-coal-200 bg-white p-6 shadow-card sm:p-8 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-xl font-bold tracking-tight text-coal-950 dark:text-slate-100">
            The traceability promise
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
<div className="rounded-2xl bg-coal-50 p-4 dark:bg-slate-800">
              <h3 className="text-sm font-semibold text-coal-950 dark:text-slate-100">
                Every number has a source
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-coal-600 dark:text-slate-300">
                Each extracted figure traces back to its document, page and the
                exact sentence — citations are part of the data model, not an
                afterthought.
              </p>
            </div>
<div className="rounded-2xl bg-coal-50 p-4 dark:bg-slate-800">
              <h3 className="text-sm font-semibold text-coal-950 dark:text-slate-100">
                Conflicts surface, not vanish
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-coal-600 dark:text-slate-300">
                When two sources disagree, the system flags the conflict instead
                of silently overwriting — a reviewer decides what stands.
              </p>
            </div>
<div className="rounded-2xl bg-coal-50 p-4 dark:bg-slate-800">
              <h3 className="text-sm font-semibold text-coal-950 dark:text-slate-100">
                Human-in-the-loop gates
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-coal-600 dark:text-slate-300">
                Draft reports sit in the review queue until an officer approves
                or sends them back with notes — automation, not autopilot.
              </p>
            </div>
          </div>
        </section>
      </main>

<footer className="border-t border-coal-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-6 text-xs text-coal-400 dark:text-slate-500">
          <p>
CoalSutra · SIH26023 prototype — Ministry of Coal /
            Coal India Ltd. · CMPDI
          </p>
          <p>Prototype data unless real documents are ingested.</p>
        </div>
      </footer>
    </>
  );
}
