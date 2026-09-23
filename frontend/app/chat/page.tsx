"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import SourceChip, {
  type EvidenceCitation,
} from "@/components/SourceChip";
import SourceEvidencePanel from "@/components/SourceEvidencePanel";
import Icon from "@/components/Icon";
import AlertBanner from "@/components/AlertBanner";
import imgProvenance from "@/app/public/img-3C.png";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const QUERY_ENDPOINT = `${API_BASE}/api/v1/query`;

type Message = {
  role: "user" | "assistant";
  text: string;
  citations: EvidenceCitation[];
};

const EMPTY_STATE: EvidenceCitation[] = [];

const SUGGESTIONS = [
  "What is the coal reserve of Jharia as of 2019?",
  "What was coal production in 2026?",
  "Report ash and moisture for Bokaro in 2021.",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<EvidenceCitation | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bootedRef = useRef(false);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      void send(q);
    }
  }, []);

  async function send(prefill?: string) {
    const question = (prefill ?? input).trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: question, citations: EMPTY_STATE }]);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(QUERY_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail ?? `Request failed (${res.status})`);
      }
      const data = await res.json();
      const answer: string = data.answer ?? "";
      const citations: EvidenceCitation[] = Array.isArray(data.citations)
        ? data.citations
        : [];
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: answer, citations },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
      e.preventDefault();
      void send();
    }
  }

  const showEmptyState = messages.length === 0 && !loading;

  return (
    <>
      <main className="mx-auto flex max-w-chat flex-col px-4 pb-6 pt-8 sm:px-6">
        {showEmptyState ? (
          <div className="flex flex-1 flex-col items-center justify-center py-20 text-center">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-faint text-accent dark:bg-accent/15 dark:text-amber-300">
              <Icon name="chat" size={22} />
            </span>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-ink dark:text-slate-100">
              Ask the corpus
            </h1>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-muted dark:text-slate-400">
              Questions are answered only from extracted, validated facts. Every
              answer lists its source documents and pages.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setInput(suggestion);
                    textareaRef.current?.focus();
                  }}
                  className="rounded-lg border border-coal-200 bg-white px-3 py-1.5 text-sm text-ink-muted shadow-card transition-colors hover:border-accent-ring hover:text-accent dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:text-white"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <Image
              src={imgProvenance}
              alt="Provenance illustration: every answer traces to its source document, page and exact snippet."
              className="mt-8 h-auto w-full max-w-xl rounded-2xl border border-coal-200 bg-white shadow-card dark:border-slate-700 dark:bg-slate-800"
            />
          </div>
        ) : (
          <div className="flex h-[calc(100dvh-9rem)] flex-col gap-4 overflow-y-auto pb-4">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed shadow-card animate-fade-in ${
                    msg.role === "user"
                      ? "rounded-br-md bg-ink text-white dark:bg-slate-100 dark:text-slate-900"
                      : "rounded-bl-md border border-coal-200 bg-white text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  {msg.role === "assistant" && (
                    <div className="mt-3 border-t border-coal-100 pt-3 dark:border-slate-800">
                      {msg.citations.length === 0 ? (
                        <div className="rounded-lg bg-gap-light px-3 py-2 text-sm text-gap dark:bg-gap/15 dark:text-amber-300">
                          <p className="flex items-center gap-1.5 font-medium">
                            <Icon name="alert" size={14} />
                            I couldn&rsquo;t find supporting documents for this
                            question.
                          </p>
                          <p className="mt-0.5 text-gap/80 dark:text-amber-300/80">
                            No extracted facts matched the query. Refine the
                            question, or ingest and validate more documents.
                          </p>
                        </div>
                      ) : (
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
                            Sources
                          </span>
                          {msg.citations.map((citation, i) => (
                            <SourceChip
                              key={i}
                              citation={citation}
                              onClick={() => setActiveCitation(citation)}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-coal-200 bg-white px-4 py-3 text-sm text-ink-muted shadow-card animate-fade-in dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                  <Icon name="refresh" size={14} className="animate-spin text-accent" />
                  Searching facts and drafting an answer…
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>
        )}

        {error && (
          <div className="mb-3">
            <AlertBanner tone="error">{error}</AlertBanner>
          </div>
        )}

        <div className="sticky bottom-0 border-t border-coal-200 bg-canvas pt-3 dark:border-slate-800 dark:bg-canvas-dark">
          <div className="flex items-end gap-2 rounded-xl border border-coal-300 bg-white p-2 shadow-card transition-colors focus-within:border-accent-ring dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-slate-500">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about reserves, production, quality…"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] text-ink outline-none placeholder:text-ink-muted/70 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
            <button
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              aria-label="Send message"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <Icon name="refresh" size={16} className="animate-spin" />
              ) : (
                <Icon name="send" size={16} />
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-ink-muted dark:text-slate-500">
            Enter or Ctrl/⌘ + Enter to send · Shift + Enter for a new line.
          </p>
        </div>
      </main>

      <SourceEvidencePanel
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </>
  );
}