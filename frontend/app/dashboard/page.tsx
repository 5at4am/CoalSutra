"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

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
  "text-coal-950 dark:text-slate-100 dark:text-slate-100",
  "text-coal-700 dark:text-slate-300",
  "text-source dark:text-emerald-400",
  "text-coal-500 dark:text-slate-400 dark:text-slate-400",
  "text-source-dark dark:text-emerald-500",
  "text-coal-800 dark:text-slate-200",
];

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${Math.round(ms)} ms`;
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-coal-400 dark:text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-coal-950 dark:text-slate-100">
        {value}
      </p>
      <p className="mt-1 text-sm text-coal-400 dark:text-slate-500">{sub}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [topicRun, setTopicRun] = useState<TopicRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
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
        if (failed.length) {
          const messages = failed.map((r) =>
            r.reason instanceof Error ? r.reason.message : "Request failed."
          );
          setError(messages.join(" · "));
        }
      } catch {
        setError("Failed to load dashboard data.");
      }
    };
    void load();
  }, []);

  const topics = topicRun?.topics ?? [];
  const maxDoc = Math.max(1, ...topics.map((t) => t.doc_count));

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

  return (
    <>
      <main className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6">
        <header>
          <h1 className="text-xl font-semibold text-coal-950 dark:text-slate-100">Dashboard</h1>
          <p className="mt-1 text-sm text-coal-500 dark:text-slate-400">
            Pipeline health and topic landscape across the ingested corpus.
          </p>
        </header>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400">
            {error}
          </div>
        )}

        {/* metrics row */}
        {metrics ? (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Documents processed"
              value={String(metrics.documents_processed)}
              sub={`${metrics.documents_total} total ingested`}
            />
            <MetricCard
              label="Avg. query time"
              value={formatMs(metrics.avg_query_ms)}
              sub={
                metrics.queries_served > 0
                  ? `across ${metrics.queries_served} questions`
                  : "ask a question in Chat to populate"
              }
            />
            <MetricCard
              label="Open conflicts"
              value={String(metrics.open_conflicts)}
              sub="awaiting human review"
            />
            <MetricCard
              label="Docs needing review"
              value={`${metrics.flagged_documents_pct}%`}
              sub="of processed documents"
            />
          </div>
        ) : (
          !error && (
            <div className="mt-6 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center text-sm text-coal-400 dark:text-slate-500 shadow-card">
              Loading metrics…
            </div>
          )
        )}

        {/* word cloud */}
        <section className="mt-6 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-card">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-coal-500 dark:text-slate-400">
              Word cloud
            </h2>
            {topicRun && (
              <span className="text-xs text-coal-400 dark:text-slate-500">
                from run #{topicRun.id} · {topics.length} topics
              </span>
            )}
          </div>
          {cloudWords.length === 0 ? (
            <p className="mt-6 text-center text-sm text-coal-400 dark:text-slate-500">
              No topic run yet — ingest documents and run a topic analysis to
              surface keyword clusters here.
            </p>
          ) : (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 py-6">
              {cloudWords.map((item, i) => (
                <span
                  key={`${item.word}-${i}`}
                  className={`font-medium leading-none ${CLOUD_PALETTE[i % CLOUD_PALETTE.length]}`}
                  style={{ fontSize: `${cloudScale(item.weight)}px` }}
                >
                  {item.word}
                </span>
              ))}
            </div>
          )}
        </section>

        {/* topic bars */}
        <section className="mt-6 rounded-2xl border border-coal-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-card">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-coal-500 dark:text-slate-400">
            Topics
          </h2>
          {topics.length === 0 ? (
            <p className="mt-6 text-center text-sm text-coal-400 dark:text-slate-500">
              No topics available yet.
            </p>
          ) : (
            <ul className="mt-5 flex flex-col gap-5">
              {topics.map((topic, i) => (
                <li key={`${topic.label}-${i}`}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-4">
                    <p className="text-sm font-medium text-coal-900 dark:text-slate-100">
                      {topic.label}
                    </p>
                    <span className="text-xs tabular-nums text-coal-400 dark:text-slate-500">
                      {topic.doc_count} document{topic.doc_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-coal-100 dark:bg-slate-800">
                    <div
                      className="h-full rounded-full bg-source"
                      style={{ width: `${(topic.doc_count / maxDoc) * 100}%` }}
                    />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {topic.top_keywords.map((keyword, j) => (
                      <span
                        key={j}
                        className="rounded-md bg-coal-100 dark:bg-slate-800 px-2 py-0.5 text-xs font-medium text-coal-600 dark:text-slate-300"
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
    </>
  );
}