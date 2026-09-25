"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import Icon from "@/components/Icon";
import PageHeader, { SectionHeader } from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import StatusBadge from "@/components/StatusBadge";
import AlertBanner from "@/components/AlertBanner";
import { btnPrimary, btnSecondary, cardBase } from "@/lib/ui";

type UsageSummary = {
  total_calls: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  avg_latency_ms: number | null;
  success_rate: number;
  failed_calls: number;
  estimated_cost_usd: number;
  by_endpoint: {
    endpoint: string;
    calls: number;
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    estimated_cost_usd: number;
    avg_latency_ms: number | null;
    success_rate: number;
  }[];
};

type UsageCall = {
  id: number;
  endpoint: string;
  prompt_label: string | null;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  success: boolean;
  error: string | null;
  created_at: string;
};

type EvalCase = {
  id: string;
  question: string;
  ok: boolean;
  retrieval_recall: number;
  values_in_retrieved: number[];
  docs_in_retrieved: string[];
  expect_refusal_is_control?: boolean;
  answer_ok?: boolean | null;
  answer?: string;
  answer_error?: string;
  refused?: boolean;
};

type EvalRun = {
  id: number;
  mode: "retrieval" | "full";
  model: string | null;
  questions_evaluated: number;
  passed: number;
  retrieval_recall: number;
  answer_accuracy: number | null;
  refusal_passed: boolean | null;
  duration_ms: number;
  created_at: string;
  per_case: EvalCase[];
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function formatUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${Math.round(ms)} ms`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  }) + ` · ${d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export default function EvaluatePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [calls, setCalls] = useState<UsageCall[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [withAnswers, setWithAnswers] = useState(false);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c, r] = await Promise.allSettled([
        apiGet<UsageSummary>("/api/v1/llm/usage/summary"),
        apiGet<UsageCall[]>("/api/v1/llm/usage/calls?limit=20"),
        apiGet<EvalRun[]>("/api/v1/llm/eval/runs?limit=12"),
      ]);
      if (s.status === "fulfilled") setSummary(s.value);
      if (c.status === "fulfilled") setCalls(c.value);
      if (r.status === "fulfilled") setRuns(r.value);
      const failed = [s, c, r].filter(
        (x): x is PromiseRejectedResult => x.status === "rejected"
      );
      setError(
        failed.length
          ? failed
              .map((x) =>
                x.reason instanceof Error ? x.reason.message : "Request failed."
              )
              .join(" · ")
          : null
      );
    } catch {
      setError("Failed to load evaluation data.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runEvaluation() {
    setRunning(true);
    setRunError(null);
    setFeedback(null);
    try {
      await apiPost<EvalRun>("/api/v1/llm/eval/run", { with_answers: withAnswers });
      setFeedback(
        withAnswers
          ? "Evaluation finished — including the LLM answer track."
          : "Evaluation finished — retrieval-only track (fast, no LLM needed)."
      );
      await load();
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Evaluation failed.");
    } finally {
      setRunning(false);
    }
  }

  const latest = runs[0] ?? null;
  const runBars = runs.slice().reverse();
  const maxAccuracy = Math.max(
    1,
    ...runs.map((r) => Math.max(r.retrieval_recall, r.answer_accuracy ?? 0))
  );

  return (
    <main className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">
      <PageHeader
        title="Evaluate & spend"
        purpose="Golden-set accuracy of the query engine, plus token, latency and cost telemetry for every LLM call."
        actions={
          <>
            <button
              onClick={() => void load()}
              className={`${btnSecondary} px-3 py-2`}
              aria-label="Refresh metrics"
            >
              <Icon name="refresh" size={15} />
              Refresh
            </button>
            <button
              onClick={() => void runEvaluation()}
              disabled={running}
              className={btnPrimary}
            >
              <Icon name="gauge" size={15} />
              {running ? "Evaluating…" : "Run evaluation"}
            </button>
          </>
        }
      />

      {error && (
        <div className="mt-4">
          <AlertBanner tone="error">{error}</AlertBanner>
        </div>
      )}
      {runError && (
        <div className="mt-4">
          <AlertBanner tone="error">{runError}</AlertBanner>
        </div>
      )}
      {feedback && (
        <div className="mt-4">
          <AlertBanner tone="success">{feedback}</AlertBanner>
        </div>
      )}

      {/* ---------- run options ---------- */}
      <section className={`${cardBase} mt-6 flex flex-col items-start justify-between gap-4 p-5 sm:flex-row sm:items-center`}>
        <div>
          <p className="text-sm font-medium text-ink dark:text-slate-100">
            Evaluation track
          </p>
          <p className="mt-0.5 text-sm text-ink-muted dark:text-slate-400">
            Retrieval-only scores your chunks without an LLM key. The full track
            also asks the model to answer and checks the answers.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2.5 text-sm text-ink dark:text-slate-200">
          <input
            type="checkbox"
            checked={withAnswers}
            onChange={(e) => setWithAnswers(e.target.checked)}
            className="h-4 w-4 rounded border-coal-300 text-accent focus:ring-accent-ring dark:border-slate-600"
          />
          Include LLM answers
        </label>
      </section>

      {/* ---------- usage KPI row ---------- */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Tokens used"
          value={summary ? formatTokens(summary.total_tokens) : "—"}
          sub={summary ? `${summary.total_calls} LLM calls recorded` : "no calls yet"}
          icon={<Icon name="layers" size={16} />}
        />
        <KpiCard
          label="Est. spend"
          value={summary ? formatUsd(summary.estimated_cost_usd) : "—"}
          sub="at configured per-token prices"
          icon={<Icon name="spark" size={16} />}
        />
        <KpiCard
          label="Avg latency"
          value={summary ? formatMs(summary.avg_latency_ms) : "—"}
          sub="per provider round-trip"
          icon={<Icon name="clock" size={16} />}
        />
        <KpiCard
          label="Success rate"
          value={summary ? pct(summary.success_rate / 100) : "—"}
          sub={summary ? `${summary.failed_calls} failed call${summary.failed_calls === 1 ? "" : "s"}` : "—"}
          tone={summary && summary.failed_calls > 0 ? "warning" : "success"}
          icon={<Icon name="check-circle" size={16} />}
        />
      </div>

      {/* ---------- accuracy ---------- */}
      <section className={`${cardBase} mt-6 p-6`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionHeader title="Model accuracy" icon="gauge" />
          {latest ? (
            <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
              run #{latest.id} · {latest.mode === "full" ? "retrieval + answers" : "retrieval-only"} · {formatTime(latest.created_at)}
            </span>
          ) : null}
        </div>

        {!latest ? (
          <div className="mt-8 flex flex-col items-center py-8 text-center">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400">
              <Icon name="gauge" size={18} />
            </span>
            <p className="mt-3 text-sm text-ink-muted dark:text-slate-400">
              No evaluation runs yet — press “Run evaluation” to score the query
              engine against the golden question set.
            </p>
          </div>
        ) : (
          <>
            {/* headline numbers for the latest run */}
            <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <div className="rounded-xl border border-coal-200 p-4 dark:border-slate-700">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                  Retrieval recall
                </p>
                <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink dark:text-slate-100">
                  {pct(latest.retrieval_recall)}
                </p>
                <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
                  {latest.passed}/{latest.questions_evaluated} cases passed
                </p>
              </div>
              <div className="rounded-xl border border-coal-200 p-4 dark:border-slate-700">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                  Answer accuracy
                </p>
                <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink dark:text-slate-100">
                  {latest.answer_accuracy === null ? "—" : pct(latest.answer_accuracy)}
                </p>
                <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
                  {latest.mode === "full" ? "LLM answer track" : "run full track to score answers"}
                </p>
              </div>
              <div className="rounded-xl border border-coal-200 p-4 dark:border-slate-700">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                  Refusal control
                </p>
                <div className="mt-1.5">
                  {latest.refusal_passed === null ? (
                    <span className="text-2xl font-semibold tabular-nums text-ink dark:text-slate-100">—</span>
                  ) : latest.refusal_passed ? (
                    <StatusBadge tone="success" label="Correctly refused" dot />
                  ) : (
                    <StatusBadge tone="danger" label="Answered anyway" dot />
                  )}
                </div>
                <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
                  out-of-corpus question
                </p>
              </div>
              <div className="rounded-xl border border-coal-200 p-4 dark:border-slate-700">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                  Run time
                </p>
                <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink dark:text-slate-100">
                  {formatMs(latest.duration_ms)}
                </p>
                <p className="mt-1 text-xs text-ink-muted dark:text-slate-500">
                  {latest.mode === "full" ? "across retrieval + answers" : "retrieval only"}
                </p>
              </div>
            </div>

            {/* accuracy-over-time bars */}
            {runs.length > 1 ? (
              <div className="mt-8">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-ink dark:text-slate-100">
                    Accuracy over runs
                  </p>
                  <span className="text-xs text-ink-muted dark:text-slate-500">
                    <span className="mr-3 inline-flex items-center gap-1.5">
                      <span aria-hidden="true" className="h-2 w-2 rounded-sm bg-source" />
                      retrieval
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span aria-hidden="true" className="h-2 w-2 rounded-sm bg-info" />
                      answers
                    </span>
                  </span>
                </div>
                <div className="mt-3 flex items-end gap-2 sm:gap-3">
                  {runBars.map((run) => (
                    <div
                      key={run.id}
                      className="flex flex-1 flex-col items-center gap-1"
                      title={`Run #${run.id} — retrieval ${pct(run.retrieval_recall)}, answers ${
                        run.answer_accuracy === null ? "n/a" : pct(run.answer_accuracy)
                      }`}
                    >
                      <div className="flex h-40 w-full items-end justify-center gap-1">
                        <div
                          className="w-6 rounded-t-md bg-source/80 dark:bg-source/70"
                          style={{ height: `${(run.retrieval_recall / maxAccuracy) * 100}%` }}
                          aria-hidden="true"
                        />
                        {run.answer_accuracy !== null && (
                          <div
                            className="w-6 rounded-t-md bg-info/80 dark:bg-info/70"
                            style={{ height: `${(run.answer_accuracy / maxAccuracy) * 100}%` }}
                            aria-hidden="true"
                          />
                        )}
                      </div>
                      <span className="text-[11px] tabular-nums text-ink-muted dark:text-slate-500">
                        #{run.id}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-ink-muted dark:text-slate-500">
                  Oldest run on the left; bar height is accuracy (0–100%).
                </p>
              </div>
            ) : null}

            {/* per-case table */}
            <div className="mt-8 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-coal-200 text-xs uppercase tracking-wide text-ink-muted dark:border-slate-700 dark:text-slate-500">
                    <th className="py-2.5 pr-4 font-medium">Case</th>
                    <th className="px-4 py-2.5 font-medium">Retrieval</th>
                    {latest.mode === "full" && (
                      <th className="px-4 py-2.5 font-medium">Answer</th>
                    )}
                    <th className="px-4 py-2.5 font-medium">Values found</th>
                    <th className="px-4 py-2.5 font-medium">Documents</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-coal-100 dark:divide-slate-800">
                  {latest.per_case.map((c) => (
                    <tr key={c.id} className="align-top">
                      <td className="max-w-[260px] py-3 pr-4">
                        <p className="font-medium text-ink dark:text-slate-100">
                          {c.expect_refusal_is_control ? "Refusal control" : c.id}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-ink-muted dark:text-slate-400">
                          {c.question}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        {c.ok ? (
                          <StatusBadge tone="success" label="passed" dot />
                        ) : (
                          <StatusBadge tone="danger" label={`failed · ${pct(c.retrieval_recall)} recall`} dot />
                        )}
                      </td>
                      {latest.mode === "full" && (
                        <td className="px-4 py-3">
                          {c.answer_error ? (
                            <span className="text-xs text-ink-muted dark:text-slate-400">
                              {c.answer_error}
                            </span>
                          ) : c.answer_ok === true ? (
                            <StatusBadge tone="success" label="correct" dot />
                          ) : (
                            <StatusBadge tone="danger" label="wrong" dot />
                          )}
                        </td>
                      )}
                      <td className="px-4 py-3 tabular-nums">
                        {c.values_in_retrieved.length === 0 ? (
                          <span className="text-xs text-ink-muted dark:text-slate-500">—</span>
                        ) : (
                          c.values_in_retrieved.join(", ")
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {c.docs_in_retrieved.length === 0 ? (
                          <span className="text-xs text-ink-muted dark:text-slate-500">—</span>
                        ) : (
                          c.docs_in_retrieved.join(", ")
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* ---------- usage by endpoint ---------- */}
      <section className={`${cardBase} mt-6 p-6`}>
        <SectionHeader
          title="Token usage by endpoint"
          icon="chart"
          meta={
            summary ? (
              <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
                est. {formatUsd(summary.estimated_cost_usd)} total · {pct(summary.success_rate / 100)} success
              </span>
            ) : undefined
          }
        />
        {!summary || summary.by_endpoint.length === 0 ? (
          <div className="mt-8 flex flex-col items-center py-8 text-center">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400">
              <Icon name="chart" size={18} />
            </span>
            <p className="mt-3 text-sm text-ink-muted dark:text-slate-400">
              No LLM calls recorded yet — ask a question in Chat or run a full
              evaluation to populate token telemetry.
            </p>
          </div>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-coal-200 text-xs uppercase tracking-wide text-ink-muted dark:border-slate-700 dark:text-slate-500">
                  <th className="py-2.5 pr-4 font-medium">Endpoint</th>
                  <th className="px-4 py-2.5 font-medium">Calls</th>
                  <th className="px-4 py-2.5 font-medium">Prompt</th>
                  <th className="px-4 py-2.5 font-medium">Completion</th>
                  <th className="px-4 py-2.5 font-medium">Est. cost</th>
                  <th className="px-4 py-2.5 font-medium">Avg latency</th>
                  <th className="px-4 py-2.5 font-medium">Success</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-coal-100 dark:divide-slate-800">
                {summary.by_endpoint.map((ep) => (
                  <tr key={ep.endpoint}>
                    <td className="py-3 pr-4 font-medium capitalize text-ink dark:text-slate-100">
                      {ep.endpoint}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{ep.calls}</td>
                    <td className="px-4 py-3 tabular-nums">{formatTokens(ep.prompt_tokens)}</td>
                    <td className="px-4 py-3 tabular-nums">{formatTokens(ep.completion_tokens)}</td>
                    <td className="px-4 py-3 tabular-nums">{formatUsd(ep.estimated_cost_usd)}</td>
                    <td className="px-4 py-3 tabular-nums">{formatMs(ep.avg_latency_ms)}</td>
                    <td className="px-4 py-3">
                      {ep.success_rate === 100 ? (
                        <StatusBadge tone="success" label="100%" dot />
                      ) : ep.success_rate > 0 ? (
                        <StatusBadge tone="warning" label={`${Math.round(ep.success_rate)}%`} dot />
                      ) : (
                        <StatusBadge tone="danger" label="0%" dot />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* recent calls */}
        <div className="mt-8">
          <SectionHeader
            title="Recent calls"
            icon="clock"
            meta={
              <span className="text-xs tabular-nums text-ink-muted dark:text-slate-500">
                {calls.length} most recent
              </span>
            }
          />
          {calls.length === 0 ? (
            <p className="mt-4 text-sm text-ink-muted dark:text-slate-400">
              Nothing recorded yet.
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-coal-200 text-xs uppercase tracking-wide text-ink-muted dark:border-slate-700 dark:text-slate-500">
                    <th className="py-2.5 pr-4 font-medium">Time</th>
                    <th className="px-4 py-2.5 font-medium">Endpoint</th>
                    <th className="px-4 py-2.5 font-medium">Label</th>
                    <th className="px-4 py-2.5 font-medium">Model</th>
                    <th className="px-4 py-2.5 font-medium">Tokens</th>
                    <th className="px-4 py-2.5 font-medium">Latency</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-coal-100 dark:divide-slate-800">
                  {calls.map((call) => (
                    <tr key={call.id} title={call.error ?? undefined}>
                      <td className="whitespace-nowrap py-3 pr-4 tabular-nums text-ink-muted dark:text-slate-400">
                        {formatTime(call.created_at)}
                      </td>
                      <td className="px-4 py-3 capitalize text-ink dark:text-slate-100">{call.endpoint}</td>
                      <td className="max-w-[220px] truncate px-4 py-3 text-ink-muted dark:text-slate-400">
                        {call.prompt_label ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-ink-muted dark:text-slate-400">{call.model}</td>
                      <td className="px-4 py-3 tabular-nums">{formatTokens(call.total_tokens)}</td>
                      <td className="px-4 py-3 tabular-nums">{formatMs(call.latency_ms)}</td>
                      <td className="px-4 py-3">
                        {call.success ? (
                          <StatusBadge tone="success" label="ok" dot />
                        ) : (
                          <StatusBadge tone="danger" label="failed" dot />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}