import { ArrowUpRight } from "lucide-react";

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconClass = "text-blue-500",
  valueClass = "",
  children,
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5 transition hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {Icon && (
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 dark:bg-zinc-900 ${iconClass}`}
            >
              <Icon size={15} />
            </div>
          )}

          <p className="text-xs font-medium text-slate-600 dark:text-zinc-400">
            {title}
          </p>
        </div>

        <ArrowUpRight
          size={14}
          className="text-slate-300 dark:text-zinc-700"
        />
      </div>

      <div className="mt-3">
        <p
          className={`text-[22px] font-semibold tracking-tight text-slate-950 dark:text-white ${valueClass}`}
        >
          {value}
        </p>

        {subtitle && (
          <p className="mt-1 text-[10px] text-slate-400 dark:text-zinc-500">
            {subtitle}
          </p>
        )}

        {children}
      </div>
    </div>
  );
}

export default StatCard;