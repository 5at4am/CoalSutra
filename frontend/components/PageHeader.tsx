import Icon, { type IconName } from "@/components/Icon";

type PageHeaderProps = {
  title: string;
  purpose: string;
  context?: React.ReactNode;
  actions?: React.ReactNode;
};

export default function PageHeader({
  title,
  purpose,
  context,
  actions,
}: PageHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink dark:text-slate-50">
          {title}
        </h1>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted dark:text-slate-400">
          {purpose}
        </p>
        {context}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </header>
  );
}

export function SectionHeader({
  title,
  meta,
  icon,
}: {
  title: string;
  meta?: React.ReactNode;
  icon?: IconName;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {icon && (
        <span className="text-coal-400 dark:text-slate-500">
          <Icon name={icon} size={16} />
        </span>
      )}
      <h2 className="text-base font-semibold text-ink dark:text-slate-100">
        {title}
      </h2>
      {meta}
    </div>
  );
}