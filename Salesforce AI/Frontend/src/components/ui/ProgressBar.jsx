function ProgressBar({
  value = 0,
  variant = "default",
  size = "sm",
  showValue = false,
}) {
  const percentage = Math.min(
    100,
    Math.max(0, Number(value) || 0)
  );

  const colors = {
    default: "bg-blue-500",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-red-500",
  };

  const sizes = {
    xs: "h-1",
    sm: "h-1.5",
    md: "h-2",
  };

  return (
    <div className="w-full">
      <div
        className={`w-full overflow-hidden rounded-full bg-slate-200 dark:bg-zinc-800 ${sizes[size]}`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${colors[variant]}`}
          style={{
            width: `${percentage}%`,
          }}
        />
      </div>

      {showValue && (
        <div className="mt-1 text-right text-[10px] text-slate-500 dark:text-zinc-500">
          {percentage}%
        </div>
      )}
    </div>
  );
}

export default ProgressBar;