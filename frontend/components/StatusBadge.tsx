type Tone = "neutral" | "info" | "warning" | "success" | "danger";

const TONES: Record<Tone, string> = {
  neutral:
    "bg-coal-100 text-coal-700 dark:bg-slate-800 dark:text-slate-300",
  info: "bg-info-soft text-info-dark dark:bg-info/15 dark:text-sky-300",
  warning: "bg-gap-light text-gap dark:bg-gap/15 dark:text-amber-300",
  success:
    "bg-source-light text-source-dark dark:bg-source/20 dark:text-emerald-300",
  danger:
    "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400",
};

export default function StatusBadge({
  tone = "neutral",
  label,
  dot = false,
}: {
  tone?: Tone;
  label: string;
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {dot && (
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${
            tone === "neutral"
              ? "bg-coal-400 dark:bg-slate-500"
              : tone === "info"
                ? "bg-info"
                : tone === "warning"
                  ? "bg-gap"
                  : tone === "success"
                    ? "bg-source"
                    : "bg-red-600"
          }`}
        />
      )}
      {label}
    </span>
  );
}