"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import BrandLogo from "@/components/BrandLogo";
import Icon from "@/components/Icon";
import { btnPrimary, inputBase } from "@/lib/ui";
import { API_BASE, fetchAuthConfig, getToken, setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [demoUsers, setDemoUsers] = useState<Record<string, string>>({});
  const [alreadyAuthed, setAlreadyAuthed] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setAlreadyAuthed(true);
      router.replace("/chat");
      return;
    }
    let alive = true;
    fetchAuthConfig()
      .then((config) => {
        if (!alive) return;
        setAuthEnabled(config.auth_enabled);
        setDemoUsers(config.demo_users ?? {});
      })
      .catch(() => {
        if (!alive) return;
        setAuthEnabled(true);
      });
    return () => {
      alive = false;
    };
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok || !body?.access_token) {
        setError(
          body?.detail ?? (res.status === 401 ? "Invalid login" : "Login failed"),
        );
        return;
      }
      setToken(body.access_token);
      router.replace("/chat");
    } catch {
      setError("Could not reach the backend. Is it running?");
    } finally {
      setBusy(false);
    }
  }

  if (alreadyAuthed) {
    return <div className="min-h-screen" />;
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-4">
      <div className="mb-6 flex flex-col items-center text-center">
        <BrandLogo subtitle="SIH 2026 · MoC / CIL" />
      </div>

      {authEnabled === false && (
        <div className="mb-4 rounded-xl border border-source/30 bg-source-light px-4 py-3 text-sm text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300">
          <p className="flex items-center gap-1.5 font-medium">
            <Icon name="shield" size={14} /> Auth is disabled
          </p>
          <p className="mt-0.5 text-xs opacity-80">
            The API is open — head straight to{" "}
            <Link href="/chat" className="underline">
              the assistant
            </Link>
            .
          </p>
        </div>
      )}

      {authEnabled !== false && (
        <form
          onSubmit={submit}
          className="rounded-2xl border border-coal-200 bg-white p-6 shadow-card dark:border-slate-700 dark:bg-slate-900"
        >
          <h1 className="text-xl font-semibold text-ink dark:text-slate-100">
            Sign in
          </h1>
          <p className="mt-1 text-sm text-ink-muted dark:text-slate-400">
            Access the reporting workspace.
          </p>

          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </div>
          )}

          <label className="mt-5 block text-sm font-medium text-ink dark:text-slate-200">
            Username
            <input
              className={`${inputBase} mt-1`}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-ink dark:text-slate-200">
            Password
            <input
              className={`${inputBase} mt-1`}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <button
            type="submit"
            disabled={busy || !username.trim() || !password}
            className={`${btnPrimary} mt-6 w-full`}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      )}

      {authEnabled === true && Object.keys(demoUsers).length > 0 && (
        <p className="mt-4 text-center text-xs text-ink-muted dark:text-slate-500">
          Demo logins:{" "}
          {Object.entries(demoUsers)
            .map(([user, pass]) => `${user} / ${pass}`)
            .join(" · ")}
        </p>
      )}
    </main>
  );
}