import Icon, { type IconName } from "@/components/Icon";

type EmptyStateProps = {
  icon?: IconName;
  title: string;
  body: string;
  action?: React.ReactNode;
};

export default function EmptyState({
  icon = "file",
  title,
  body,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-coal-200 bg-white px-6 py-12 text-center shadow-card dark:border-slate-700 dark:bg-slate-900">
      <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-coal-100 text-coal-500 dark:bg-slate-800 dark:text-slate-400">
        <Icon name={icon} size={20} />
      </span>
      <h3 className="mt-4 text-sm font-semibold text-ink dark:text-slate-100">
        {title}
      </h3>
      <p className="mt-1 max-w-md text-sm leading-relaxed text-ink-muted dark:text-slate-400">
        {body}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}