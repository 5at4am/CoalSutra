"use client";

import Icon from "@/components/Icon";

type Tone = "error" | "info" | "success" | "warning";

const TONES: Record<
  Tone,
  { wrap: string; icon: "alert" | "info" | "check-circle" }
> = {
  error: {
    wrap: "border-red-200 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300",
    icon: "alert",
  },
  warning: {
    wrap: "border-gap/25 bg-gap-light text-gap dark:border-gap/40 dark:bg-gap/15 dark:text-amber-300",
    icon: "alert",
  },
  success: {
    wrap: "border-source/25 bg-source-light text-source-dark dark:border-source/40 dark:bg-source/15 dark:text-emerald-300",
    icon: "check-circle",
  },
  info: {
    wrap: "border-info-border bg-info-soft text-info-dark dark:border-info/40 dark:bg-info/15 dark:text-sky-300",
    icon: "info",
  },
};

export default function AlertBanner({
  tone = "info",
  children,
  className = "",
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  const t = TONES[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm ${t.wrap} ${className}`}
    >
      <Icon name={t.icon} size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}