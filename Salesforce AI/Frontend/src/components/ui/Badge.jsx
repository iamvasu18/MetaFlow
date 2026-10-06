function Badge({
  children,
  variant = "neutral",
  dot = false,
}) {
  const variants = {
    neutral:
      "bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-300",

    blue:
      "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",

    success:
      "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",

    warning:
      "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",

    danger:
      "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400",

    purple:
      "bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400",
  };

  const dots = {
    neutral: "bg-slate-400",
    blue: "bg-blue-500",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-red-500",
    purple: "bg-purple-500",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-medium ${variants[variant]}`}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${dots[variant]}`}
        />
      )}

      {children}
    </span>
  );
}

export default Badge;