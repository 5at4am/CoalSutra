"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import BrandLogo from "@/components/BrandLogo";
import Icon, { type IconName } from "@/components/Icon";
import { clearToken, getToken } from "@/lib/auth";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Overview", icon: "home" },
  { href: "/ingest", label: "Ingest", icon: "upload" },
  { href: "/chat", label: "Chat", icon: "chat" },
  { href: "/reports", label: "Reports", icon: "report" },
  { href: "/dashboard", label: "Dashboard", icon: "chart" },
  { href: "/review", label: "Review Queue", icon: "review" },
];

export default function SidebarLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    setHasToken(Boolean(getToken()));
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (pathname === "/login") {
    return <div className="min-h-screen">{children}</div>;
  }

  function signOut() {
    clearToken();
    router.replace("/login");
  }

  const navList = (
    <nav className="mt-6 flex flex-col gap-1" aria-label="Primary">
      {NAV.map((item) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active
                ? "bg-ink text-white dark:bg-white/10 dark:text-white"
                : "text-coal-600 hover:bg-coal-100 hover:text-coal-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
            }`}
          >
            {active && (
              <span
                aria-hidden="true"
                className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent-ring"
              />
            )}
            <Icon
              name={item.icon}
              size={16}
              className={active ? "opacity-100" : "opacity-70"}
            />
            {item.label}
            {item.href === "/review" && (
              <span
                aria-hidden="true"
                className="ml-auto h-1.5 w-1.5 rounded-full bg-accent-ring"
              />
            )}
          </Link>
        );
      })}
    </nav>
  );

  const sidebarFooter = (
    <div className="flex items-center gap-3 border-t border-coal-200 px-5 py-4 dark:border-slate-800">
      <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-source-light text-source dark:bg-source/20 dark:text-emerald-300">
        <Icon name="shield" size={15} />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-ink dark:text-slate-200">
          CMPDI Reporting Assistant
        </p>
        <p className="text-[11px] leading-snug text-ink-muted dark:text-slate-500">
          SIH 2026 · Ministry of Coal
        </p>
      </div>
      <span className="ml-auto">
        {hasToken ? (
          <button
            type="button"
            onClick={signOut}
            title="Sign out"
            aria-label="Sign out"
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-coal-500 transition-colors hover:bg-coal-100 hover:text-coal-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            <Icon name="logout" size={15} />
          </button>
        ) : (
          <ThemeToggle />
        )}
      </span>
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* ---------- desktop sidebar ---------- */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-coal-200 bg-white lg:flex dark:border-slate-800 dark:bg-slate-900">
        <div className="px-5 pt-5">
          <BrandLogo subtitle="SIH 2026 · MoC / CIL" />
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-2">{navList}</div>
        {sidebarFooter}
      </aside>

      {/* ---------- mobile top bar ---------- */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-coal-200 bg-canvas/90 px-4 py-3 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-900/90">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
            aria-expanded={open}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-coal-200 bg-white text-coal-600 transition-colors hover:bg-coal-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            <Icon name="menu" size={18} />
          </button>
          <BrandLogo />
        </div>
        <ThemeToggle />
      </header>

      {/* ---------- mobile drawer ---------- */}
      <div
        className={`fixed inset-0 z-40 bg-slate-950/45 lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-coal-200 bg-white transition-transform duration-200 ease-out lg:hidden dark:border-slate-800 dark:bg-slate-900 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 pt-5">
          <BrandLogo onClick={() => setOpen(false)} />
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-coal-500 transition-colors hover:bg-coal-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-2" onClick={() => setOpen(false)}>
          {navList}
        </div>
        {sidebarFooter}
      </aside>

      {/* ---------- content ---------- */}
      <div className="lg:pl-60">{children}</div>
    </div>
  );
}