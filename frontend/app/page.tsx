"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { apiGet } from "@/lib/api";
import Icon, { type IconName } from "@/components/Icon";
import AlertBanner from "@/components/AlertBanner";
import StatusBadge from "@/components/StatusBadge";
import KpiCard from "@/components/KpiCard";
import { btnSecondary } from "@/lib/ui";
import imgHeroJourney from "@/app/public/img-3A.png";
import imgSecurity from "@/app/public/img-3E.png";

type MetricStat = {
  label: string;
  value: string;
  tone: "default" | "warning" | "info" | "success";
  icon: IconName;
};

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

const MODULES: {
  href: string;
  icon: IconName;
  title: string;
  description: string;
  points: string[];
  cta: string;
}[] = [
  {
    href: "/ingest",
    icon: "upload",
    title: "Ingest",
    description:
      "Upload scanned & born-digital PDFs, images, or spreadsheets. The pipeline classifies each file and routes it to the right extractor automatically.",
    points: ["Scanned vs digital routing", "OCR-scalable providers", "Upload in bulk"],
    cta: "Upload documents",
  },
  {
    href: "/chat",
    icon: "chat",
    title: "Ask the corpus",
    description:
      "Ground-RAG answers over the validated store — every claim is answered only from retrieved chunks and cites its source document and page.",
    points: ["Cited answers, no hallucination", "Honest no-evidence state", "Source viewer panel"],
    cta: "Ask a question",
  },
  {
    href: "/reports",
    icon: "report",
    title: "Auto reports",
    description:
      "Generate structured reports from validated facts with template-driven sections, then export them straight to PDF.",
    points: ["3 report templates", "Every figure cited", "PDF export built in"],
    cta: "Draft a report",
  },
  {
    href: "/dashboard",
    icon: "chart",
    title: "Word cloud & topics",
    description:
      "See the corpus at a glance — terms, topic clusters and document health without reading every file.",
    points: ["Live word cloud", "Topic clustering", "Document status metrics"],
    cta: "Open dashboard",
  },
  {
    href: "/review",
    icon: "review",
    title: "Review queue",
    description:
      "Cross-source conflicts are flagged, never silently overwritten. Decide which fact stands — or keep both with a note.",
    points: ["Conflict detection", "Keep A / B / both / neither", "Report approval gate"],
    cta: "Review conflicts",
  },
];

const PIPELINE: { icon: IconName; title: string; text: string }[] = [
  { icon: "upload", title: "Ingest", text: "Files land in the system; routing decides scanned vs digital." },
  { icon: "file", title: "Extract", text: "Text, tables and numbers become one normalized schema." },
  { icon: "shield", title: "Validate", text: "Cross-source checks flag value conflicts for a human." },
  { icon: "layers", title: "Store", text: "Facts in Postgres, embeddings in the vector store." },
  { icon: "spark", title: "Serve", text: "Query (cited), reports, topics — all from the same store." },
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

  const stats: MetricStat[] = metrics
    ? [
        { label: "Documents ingested", value: String(metrics.documents_total), tone: "default", icon: "file" },
        { label: "Facts extracted", value: String(totalFacts), tone: "success", icon: "layers" },
        {
          label: "Open conflicts",
          value: String(metrics.open_conflicts),
          tone: metrics.open_conflicts > 0 ? "warning" : "success",
          icon: "review",
        },
        { label: "Flagged docs", value: `${Math.round(metrics.flagged_documents_pct)}%`, tone: "info", icon: "shield" },
        { label: "Avg query time", value: metrics.avg_query_ms == null ? "—" : `${Math.round(metrics.avg_query_ms)} ms`, tone: "default", icon: "clock" },
        { label: "Queries answered", value: String(metrics.queries_served), tone: "default", icon: "chat" },
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
        <section className="relative mt-8 overflow-hidden rounded-3xl border border-coal-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
          <span
            aria-hidden="true"
            className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-accent via-accent-ring to-source"
          />
          <div className="grid items-center gap-8 px-6 py-12 sm:px-12 sm:py-14 lg:grid-cols-[7fr_5fr] lg:gap-12">
            <div className="max-w-3xl">
              <p className="inline-flex items-center gap-2 rounded-full border border-coal-200 bg-canvas px-3 py-1 text-xs font-medium tracking-wide text-ink-muted dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                <span className="h-1.5 w-1.5 rounded-full bg-source" />
                Smart India Hackathon 2026 · Ministry of Coal / Coal India Ltd.
              </p>
              <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight text-ink dark:text-slate-50 sm:text-5xl">
                From scattered mining documents
                <span className="block text-ink-muted dark:text-slate-400">
                  to traceable, queryable data.
                </span>
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-muted dark:text-slate-400">
                CMPDI and its subsidiaries sit on decades of geological reports,
                scanned PDFs, maps and spreadsheets. This platform ingests them,
                extracts structured facts, flags conflicts instead of guessing, and
                powers cited answers, auto-generated reports and corpus-wide topic
                analysis.
              </p>

              <form
                onSubmit={ask}
                className="mt-8 flex max-w-xl items-center gap-2 rounded-2xl border border-coal-300 bg-white p-2 shadow-card transition-colors focus-within:border-accent-ring dark:border-slate-700 dark:bg-slate-950"
              >
                <Icon name="search" size={16} className="ml-3 shrink-0 text-ink-muted dark:text-slate-500" />
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="What is the coal reserve of Jharia as of 2019?"
                  className="flex-1 bg-transparent px-2 py-2 text-[15px] text-ink outline-none placeholder:text-ink-muted/70 dark:text-slate-100 dark:placeholder:text-slate-500"
                />
                <button
                  type="submit"
                  className="shrink-0 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
                >
                  Ask
                </button>
              </form>

              <div className="mt-6 flex flex-wrap gap-3">
                <a
                  href="/ingest"
                  className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-strong"
                >
                  <Icon name="upload" size={16} />
                  Ingest documents
                </a>
                <a
                  href="/chat"
                  className="inline-flex items-center gap-2 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                >
                  Explore the corpus
                </a>
              </div>
            </div>

            <figure className="hidden lg:block">
              <Image
                src={imgHeroJourney}
                alt="Illustration of the platform journey: scattered documents are ingested, extracted into structured facts, reviewed by experts and served as cited reports."
                priority
                className="rounded-2xl border border-coal-200 bg-white shadow-card dark:border-slate-700 dark:bg-slate-800"
                sizes="(min-width: 1024px) 40vw, 100vw"
              />
              <figcaption className="mt-2 flex items-center gap-1.5 text-xs text-ink-muted dark:text-slate-500">
                <Icon name="layers" size={12} />
                Scattered documents → traceable intelligence, end to end.
              </figcaption>
            </figure>
          </div>
        </section>

        {/* ---------- live stats band ---------- */}
        <section className="mt-8">
          {backendUp === null ? null : backendUp ? (
            <>
              <div className="mb-4 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-source" />
                <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted dark:text-slate-400">
                  Live corpus status
                </h2>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {stats.map((stat) => (
                  <KpiCard
                    key={stat.label}
                    label={stat.label}
                    value={stat.value}
                    tone={stat.tone}
                    icon={<Icon name={stat.icon} size={16} />}
                  />
                ))}
              </div>
              {docs && docs.length > 0 && (
                <div className="mt-4 rounded-2xl border border-coal-200 bg-white p-4 shadow-card dark:border-slate-700 dark:bg-slate-900">
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                    Recently ingested
                  </p>
                  <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                    {docs.slice(0, 4).map((doc) => (
                      <li
                        key={doc.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-coal-100 px-3 py-2 text-sm dark:border-slate-800"
                      >
                        <span className="truncate text-ink dark:text-slate-200">{doc.filename}</span>
                        <span className="flex shrink-0 items-center gap-2">
                          <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
                            {doc.fact_count} fact{doc.fact_count === 1 ? "" : "s"}
                          </span>
                          <StatusBadge
                            label={doc.status}
                            tone={
                              doc.status === "processed"
                                ? "success"
                                : doc.status === "failed"
                                  ? "danger"
                                  : doc.status === "processing"
                                    ? "warning"
                                    : "neutral"
                            }
                            dot
                          />
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <AlertBanner tone="warning">
              Backend is offline right now — start it with{" "}
              <code className="rounded bg-white/60 px-1.5 py-0.5 font-mono text-xs dark:bg-white/10">
                uvicorn app.main:app --reload
              </code>{" "}
              from <code className="rounded bg-white/60 px-1.5 py-0.5 font-mono text-xs dark:bg-white/10">backend/</code>.
              The modules below are always ready to explore.
            </AlertBanner>
          )}
        </section>

        {/* ---------- pipeline ---------- */}
        <section className="mt-14">
          <h2 className="text-2xl font-bold tracking-tight text-ink dark:text-slate-100">
            How it works
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted dark:text-slate-400">
            One backbone shared by every screen: ingest → extract → validate →
            store → serve. Nothing is guesswork — numbers carry their source.
          </p>
          <ol className="mt-6 grid gap-3 md:grid-cols-5">
            {PIPELINE.map((p, i) => (
              <li
                key={p.title}
                className={`relative rounded-2xl border border-coal-200 bg-white p-4 shadow-card dark:border-slate-700 dark:bg-slate-900 ${
                  i < PIPELINE.length - 1 ? "md:pb-6" : ""
                }`}
              >
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-accent-faint text-accent dark:bg-accent/15 dark:text-amber-300">
                  <Icon name={p.icon} size={16} />
                </span>
                <h3 className="mt-3 text-sm font-semibold text-ink dark:text-slate-100">
                  {i + 1}. {p.title}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted dark:text-slate-400">
                  {p.text}
                </p>
                {i < PIPELINE.length - 1 && (
                  <span className="absolute -right-[15px] top-1/2 z-10 hidden -translate-y-1/2 text-coal-300 md:inline dark:text-slate-600">
                    <Icon name="chevron-right" size={16} />
                  </span>
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* ---------- modules ---------- */}
        <section className="mt-14">
          <h2 className="text-2xl font-bold tracking-tight text-ink dark:text-slate-100">
            What you can do
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted dark:text-slate-400">
            Five tools over the same validated store — each one demonstrates a
            mandated SIH deliverable.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((m) => (
              <a
                key={m.title}
                href={m.href}
                className="group flex flex-col rounded-2xl border border-coal-200 bg-white p-5 shadow-card transition-colors hover:border-coal-300 hover:shadow-pop dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600 dark:hover:bg-slate-800"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-coal-600 transition-colors group-hover:bg-accent-faint group-hover:text-accent dark:bg-slate-800 dark:text-slate-300 dark:group-hover:bg-accent/15 dark:group-hover:text-amber-300">
                  <Icon name={m.icon} size={18} />
                </div>
                <h3 className="mt-3 text-base font-semibold text-ink dark:text-slate-100">
                  {m.title}
                </h3>
                <p className="mt-1 flex-1 text-sm leading-relaxed text-ink-muted dark:text-slate-400">
                  {m.description}
                </p>
                <ul className="mt-3 grid gap-1">
                  {m.points.map((point) => (
                    <li
                      key={point}
                      className="flex items-center gap-2 text-xs text-ink-muted dark:text-slate-300"
                    >
                      <Icon name="check" size={13} className="text-source dark:text-emerald-400" />
                      {point}
                    </li>
                  ))}
                </ul>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent transition-colors group-hover:text-accent-strong dark:text-amber-300 dark:group-hover:text-amber-200">
                  {m.cta}
                  <Icon name="chevron-right" size={14} />
                </span>
              </a>
            ))}
          </div>
        </section>

        {/* ---------- traceability promise ---------- */}
        <section className="mt-14 rounded-3xl border border-coal-200 bg-white p-6 shadow-card sm:p-8 dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-xl font-bold tracking-tight text-ink dark:text-slate-100">
            The traceability promise
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl bg-canvas p-4 dark:bg-slate-800">
              <Icon name="source" size={18} className="text-source dark:text-emerald-400" />
              <h3 className="mt-2.5 text-sm font-semibold text-ink dark:text-slate-100">
                Every number has a source
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted dark:text-slate-300">
                Each extracted figure traces back to its document, page and the
                exact sentence — citations are part of the data model, not an
                afterthought.
              </p>
            </div>
            <div className="rounded-2xl bg-canvas p-4 dark:bg-slate-800">
              <Icon name="alert" size={18} className="text-gap dark:text-amber-400" />
              <h3 className="mt-2.5 text-sm font-semibold text-ink dark:text-slate-100">
                Conflicts surface, not vanish
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted dark:text-slate-300">
                When two sources disagree, the system flags the conflict instead
                of silently overwriting — a reviewer decides what stands.
              </p>
            </div>
            <div className="rounded-2xl bg-canvas p-4 dark:bg-slate-800">
              <Icon name="shield" size={18} className="text-info dark:text-sky-400" />
              <h3 className="mt-2.5 text-sm font-semibold text-ink dark:text-slate-100">
                Human-in-the-loop gates
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted dark:text-slate-300">
                Draft reports sit in the review queue until an officer approves
                or sends them back with notes — automation, not autopilot.
              </p>
            </div>
          </div>
        </section>

        {/* ---------- security & governance ---------- */}
        <section className="mt-14 grid items-center gap-8 lg:grid-cols-[5fr_7fr] lg:gap-12">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-coal-200 bg-white px-3 py-1 text-xs font-medium uppercase tracking-wide text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
              <Icon name="shield" size={12} />
              Security &amp; governance
            </span>
            <h2 className="mt-4 text-2xl font-bold tracking-tight text-ink dark:text-slate-100">
              Built for the scrutiny of a public-sector workflow
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted dark:text-slate-400">
              The platform treats every figure as evidence in an auditable
              record — access, tenacity and approvals are first-class, not add-ons.
            </p>
            <ul className="mt-5 grid gap-3 sm:grid-cols-2">
              {[
                {
                  icon: "shield" as const,
                  title: "Access control & roles",
                  text: "Named reviewers gate conflict resolution and report approvals.",
                },
                {
                  icon: "clock" as const,
                  title: "Encryption",
                  text: "Traffic encrypted in transit; at-rest encryption planned for production hosting.",
                },
                {
                  icon: "file" as const,
                  title: "Audit trail",
                  text: "Every decision is recorded with who, when and what was kept or rejected.",
                },
                {
                  icon: "layers" as const,
                  title: "Versioning & approval",
                  text: "Reports advance draft → reviewed → final; nothing is silently overwritten.",
                },
              ].map((item) => (
                <li key={item.title} className="flex gap-3">
                  <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-info-soft text-info dark:bg-info/15 dark:text-sky-300">
                    <Icon name={item.icon} size={15} />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-ink dark:text-slate-100">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-sm leading-relaxed text-ink-muted dark:text-slate-300">
                      {item.text}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <figure>
            <Image
              src={imgSecurity}
              alt="Secure workflow illustration showing access control, encryption, audit logs, versioning and expert approval."
              className="rounded-2xl border border-coal-200 bg-white shadow-card dark:border-slate-700 dark:bg-slate-800"
              sizes="(min-width: 1024px) 50vw, 100vw"
            />
            <figcaption className="mt-2 flex items-center gap-1.5 text-xs text-ink-muted dark:text-slate-500">
              <Icon name="shield" size={12} />
              Governance around data, not just dashboards.
            </figcaption>
          </figure>
        </section>
      </main>

      <footer className="border-t border-coal-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-6 text-xs text-ink-muted dark:text-slate-500">
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