"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { apiGet } from "@/lib/api";
import Icon from "@/components/Icon";
import PageHeader, { SectionHeader } from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import AlertBanner from "@/components/AlertBanner";
import { btnSecondary, cardBase } from "@/lib/ui";
import imgTopics from "@/app/public/img-3F.png";

type Metrics = {
  documents_total: number;
  documents_processed: number;
  open_conflicts: number;
  flagged_documents_pct: number;
  avg_query_ms: number | null;
  queries_served: number;
};

type Topic = {
  label: string;
  top_keywords: string[];
  doc_count: number;
};

type TopicRun = {
  id: number;
  corpus_filter: Record<string, unknown>;
  generated_at: string;
  topics: Topic[];
};

const CLOUD_PALETTE = [
  "text-ink dark:text-slate-100",
  "text-source dark:text-emerald-400",
  "text-gap dark:text-amber-300",
  "text-info dark:text-sky-400",
  "text-coal-800 dark:text-slate-300",
  "text-source-dark dark:text-emerald-500",
];

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${Math.round(ms)} ms`;
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [topicRun, setTopicRun] = useState<TopicRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, t] = await Promise.allSettled([
        apiGet<Metrics>("/api/v1/metrics/summary"),
        apiGet<TopicRun>("/api/v1/topics/latest"),
      ]);
      if (m.status === "fulfilled") setMetrics(m.value);
      if (t.status === "fulfilled") setTopicRun(t.value);
      const failed = [m, t].filter(
        (r): r is PromiseRejectedResult => r.status === "rejected"
      );
      setError(
        failed.length
          ? failed
              .map((r) =>
                r.reason instanceof Error ? r.reason.message : "Request failed."
              )
              .join(" · ")
          : null
      );
    } catch {
      setError("Failed to load dashboard data.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const topics = topicRun?.topics ?? [];
  const maxDoc = Math.max(1, ...topics.map((t) => t.doc_count));
  const topicCount = topicRun?.topics?.length ?? 0;

  const cloudWords: { word: string; weight: number }[] = [];
  const seen = new Map<string, number>();
  for (const topic of topics) {
    for (const keyword of topic.top_keywords) {
      const weight = topic.doc_count;
      const prev = seen.get(keyword) ?? 0;
      if (weight > prev) {
        seen.set(keyword, weight);
        cloudWords.push({ word: keyword, weight });
      }
    }
  }
  const cloudScale = (weight: number) => {
    const minW = Math.min(...cloudWords.map((w) => w.weight), weight);
    const maxW = Math.max(...cloudWords.map((w) => w.weight), weight);
    const t = maxW === minW ? 0.5 : (weight - minW) / (maxW - minW);
    return 16 + Math.round(t * 26);
  };

  const topicGlossary = new Set<string>();
  for (const topic of topics) for (const kw of topic.top_keywords) topicGlossary.add(kw);

  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">
      <PageHeader
        title="Dashboard"
        purpose="Pipeline health and topic landscape across the ingested corpus."
        actions={
          <button onClick={() => void load()} className={`${btnSecondary} px-3 py-2`}>
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

      {/* ---------- metrics row ---------- */}
      {metrics ? (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Documents processed"
            value={String(metrics.documents_processed)}
            sub={`${metrics.documents_total} total ingested`}
            icon={<Icon name="file" size={16} />}
          />
          <KpiCard
            label="Avg. query time"
            value={formatMs(metrics.avg_query_ms)}
            sub={
              metrics.queries_served > 0
                ? `across ${metrics.queries_served} questions`
                : "ask a question in Chat to populate"
            }
            icon={<Icon name="clock" size={16} />}
            tone={metrics.avg_query_ms !== null && metrics.avg_query_ms > 3000 ? "warning" : "info"}
          />
          <KpiCard
            label="Open conflicts"
            value={String(metrics.open_conflicts)}
            sub="awaiting human review"
            tone={metrics.open_conflicts > 0 ? "warning" : "success"}
            icon={<Icon name="review" size={16} />}
          />
          <KpiCard
            label="Docs needing review"
            value={`${metrics.flagged_documents_pct}%`}
            sub="of processed documents"
            icon={<Icon name="shield" size={16} />}
          />
        </div>
      ) : (
        !error && (
          <div className="mt-6 flex items-center justify-center gap-2 rounded-2xl border border-coal-200 bg-white p-10 text-sm text-ink-muted shadow-card dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            <Icon name="refresh" size={14} className="animate-spin" />
            Loading metrics…
          </div>
        )
      )}

      {/* ---------- topic intelligence explainer ---------- */}
      <section className={`${cardBase} mt-6 flex flex-col gap-6 p-5 lg:flex-row lg:items-center lg:gap-8`}>
        <Image
          src={imgTopics}
          alt="Topic intelligence illustration: a word cloud of frequent terms, topic clusters grouping related documents, and filters by document, year, block or source."
          className="w-full rounded-xl border border-coal-200 bg-canvas lg:w-3/5 dark:border-slate-700 dark:bg-slate-800"
          sizes="(min-width: 1024px) 55vw, 100vw"
        />
        <div className="lg:flex-1">
          <SectionHeader title="Topics & word cloud" icon="spark" />
          <p className="mt-2 text-sm leading-relaxed text-ink-muted dark:text-slate-400">
            The topic view turns the corpus into navigable clusters instead of
            forcing you to read every file.
          </p>
          <ul className="mt-3 grid gap-2">
            {[
              "The word cloud weights terms by how many documents they anchor.",
              "Topics group documents into related themes — reserves, production, quality, blocks.",
              "Every keyword stays traceable to the documents it came from.",
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
      </section>

      {/* ---------- word cloud ---------- */}
      <section className={`${cardBase} mt-6 p-6`}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <SectionHeader title="Word cloud" icon="spark" />
          {topicRun && (
            <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
              from run #{topicRun.id} · {topicCount} topic{topicCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
        {cloudWords.length === 0 ? (
          <div className="mt-8 flex flex-col items-center py-8 text-center">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400">
              <Icon name="spark" size={18} />
            </span>
            <p className="mt-3 text-sm text-ink-muted dark:text-slate-400">
              No topic run yet — ingest documents and run a topic analysis to
              surface keyword clusters here.
            </p>
          </div>
        ) : (
          <>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-y border-coal-100 py-8 dark:border-slate-800">
              {cloudWords.map((item, i) => (
                <span
                  key={`${item.word}-${i}`}
                  className={`font-semibold leading-none ${CLOUD_PALETTE[i % CLOUD_PALETTE.length]}`}
                  style={{ fontSize: `${cloudScale(item.weight)}px` }}
                  title={`appears in ${item.weight} document${item.weight === 1 ? "" : "s"}`}
                >
                  {item.word}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-ink-muted dark:text-slate-500">
              Font size reflects how many documents a keyword anchors; one word
              per topic (its top keyword).
            </p>
          </>
        )}
      </section>

      {/* ---------- topic bars ---------- */}
      <section className={`${cardBase} mt-6 p-6`}>
        <SectionHeader
          title="Topics"
          icon="chart"
          meta={
            topicCount > 0 ? (
              <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
                {topicGlossary.size} unique keywords across topics
              </span>
            ) : undefined
          }
        />
        {topics.length === 0 ? (
          <div className="mt-8 flex flex-col items-center py-8 text-center">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400">
              <Icon name="chart" size={18} />
            </span>
            <p className="mt-3 text-sm text-ink-muted dark:text-slate-400">
              No topics available yet — run a topic analysis on the corpus to
              populate this view.
            </p>
          </div>
        ) : (
          <ul className="mt-5 flex flex-col gap-5">
            {topics.map((topic, i) => (
              <li key={`${topic.label}-${i}`}>
                <div className="mb-1.5 flex items-baseline justify-between gap-4">
                  <p className="flex items-center gap-2 text-sm font-medium text-ink dark:text-slate-100">
                    <span
                      aria-hidden="true"
                      className={`h-2 w-2 shrink-0 rounded-full ${i % 2 === 0 ? "bg-source" : "bg-info"}`}
                    />
                    Topic {i + 1}: {topic.label}
                  </p>
                  <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
                    {topic.doc_count} document{topic.doc_count === 1 ? "" : "s"}
                  </span>
                </div>
                <div
                  className="h-2.5 w-full overflow-hidden rounded-full bg-coal-100 dark:bg-slate-800"
                  role="progressbar"
                  aria-valuenow={(topic.doc_count / maxDoc) * 100}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${topic.label} share of documents`}
                >
                  <div
                    className={`h-full rounded-full ${i % 2 === 0 ? "bg-source" : "bg-info"}`}
                    style={{ width: `${(topic.doc_count / maxDoc) * 100}%` }}
                  />
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {topic.top_keywords.map((keyword, j) => (
                    <span
                      key={j}
                      className="rounded-md bg-coal-100 px-2 py-0.5 text-xs font-medium text-ink-muted dark:bg-slate-800 dark:text-slate-300"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}