import {
  Loader2,
} from "lucide-react";

function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  icon: Icon,
  type = "button",
  className = "",
  onClick,
}) {
  const variants = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",

    secondary:
      "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800",

    ghost:
      "text-slate-600 hover:bg-slate-100 dark:text-zinc-300 dark:hover:bg-zinc-900",

    danger:
      "bg-red-600 text-white hover:bg-red-700",

    success:
      "bg-emerald-600 text-white hover:bg-emerald-700",
  };

  const sizes = {
    sm: "h-8 px-3 text-xs",
    md: "h-9 px-4 text-sm",
    lg: "h-10 px-5 text-sm",
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all",
        "focus:outline-none focus:ring-2 focus:ring-blue-500/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      ].join(" ")}
    >
      {loading ? (
        <Loader2
          size={15}
          className="animate-spin"
        />
      ) : (
        Icon && <Icon size={15} />
      )}

      {children}
    </button>
  );
}

export default Button;