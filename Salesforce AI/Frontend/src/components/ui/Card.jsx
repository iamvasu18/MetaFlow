function Card({
  children,
  title,
  description,
  icon: Icon,
  action,
  className = "",
}) {
  return (
    <section
      className={[
        "rounded-xl border border-slate-200 bg-white",
        "dark:border-zinc-800 dark:bg-zinc-950",
        className,
      ].join(" ")}
    >
      {(title || action) && (
        <div className="flex items-start justify-between border-b border-slate-100 px-4 py-3 dark:border-zinc-800">
          <div className="flex items-start gap-2">
            {Icon && (
              <div className="mt-0.5 text-blue-500">
                <Icon size={15} />
              </div>
            )}

            <div>
              {title && (
                <h2 className="text-xs font-semibold text-slate-900 dark:text-white">
                  {title}
                </h2>
              )}

              {description && (
                <p className="mt-0.5 text-[10px] text-slate-400 dark:text-zinc-500">
                  {description}
                </p>
              )}
            </div>
          </div>

          {action}
        </div>
      )}

      <div className="p-3.5">
        {children}
      </div>
    </section>
  );
}

export default Card;