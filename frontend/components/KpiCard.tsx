type KpiCardProps = {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "warning" | "info" | "success";
  icon?: React.ReactNode;
};

const TONE_VALUE: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  default: "text-ink dark:text-slate-100",
  warning: "text-gap dark:text-amber-300",
  info: "text-info-dark dark:text-sky-300",
  success: "text-source-dark dark:text-emerald-300",
};

const TONE_BADGE: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  default: "bg-coal-100 text-coal-600 dark:bg-slate-800 dark:text-slate-400",
  warning: "bg-gap-light text-gap dark:bg-gap/15 dark:text-amber-300",
  info: "bg-info-soft text-info-dark dark:bg-info/15 dark:text-sky-300",
  success: "bg-source-light text-source-dark dark:bg-source/15 dark:text-emerald-300",
};

export default function KpiCard({
  label,
  value,
  sub,
  tone = "default",
  icon,
}: KpiCardProps) {
  const valueTone = icon === undefined ? tone : "default";
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-coal-200 bg-white p-4 shadow-card transition-colors hover:border-coal-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600">
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted dark:text-slate-500">
          {label}
        </p>
        <p
          className={`mt-1.5 text-2xl font-semibold tracking-tight tabular-nums ${TONE_VALUE[valueTone]}`}
        >
          {value}
        </p>
        {sub && (
          <p className="mt-1 truncate text-xs text-ink-muted dark:text-slate-500">
            {sub}
          </p>
        )}
      </div>
      {icon && (
        <span
          className={`mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${TONE_BADGE[tone]}`}
        >
          {icon}
        </span>
      )}
    </div>
  );
}