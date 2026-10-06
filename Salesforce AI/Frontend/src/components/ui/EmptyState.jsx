import {
  Database,
} from "lucide-react";

function EmptyState({
  icon: Icon = Database,
  title,
  description,
  action,
}) {
  return (
    <div className="flex min-h-[150px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-400 dark:bg-zinc-900 dark:text-zinc-600">
        <Icon size={19} />
      </div>

      {title && (
        <h3 className="mt-3 text-sm font-semibold text-slate-700 dark:text-zinc-300">
          {title}
        </h3>
      )}

      {description && (
        <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500 dark:text-zinc-500">
          {description}
        </p>
      )}

      {action && (
        <div className="mt-4">
          {action}
        </div>
      )}
    </div>
  );
}

export default EmptyState;