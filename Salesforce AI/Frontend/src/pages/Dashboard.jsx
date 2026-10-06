import { NavLink, Outlet } from "react-router-dom";
import { RefreshCw } from "lucide-react";

const tabs = [
  {
    label: "Overview",
    path: "/dashboard/overview",
  },
  {
    label: "Licenses & Users",
    path: "/dashboard/licenses",
  },
  {
    label: "Limits & Storage",
    path: "/dashboard/limits",
  },
  {
    label: "Metadata",
    path: "/dashboard/metadata",
  },
];

function Dashboard() {
  return (
    <div className="min-h-[calc(100vh-56px)] bg-white dark:bg-zinc-950">
      {/* Sticky Dashboard Header */}
      <div className="sticky top-0 z-30 border-b border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95">
        <div className="mx-auto max-w-[1600px] px-5 pt-4">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Dashboard
              </h1>

              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                Your Salesforce org at a glance
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span className="hidden text-[10px] text-zinc-500 sm:block">
                Synced 10/6/2026, 10:31:11 am
              </span>

              <button className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800">
                <RefreshCw size={12} />
                Sync
              </button>
            </div>
          </div>

          {/* Dashboard tabs */}
          <nav className="mt-3 flex gap-5 overflow-x-auto">
            {tabs.map((tab) => (
              <NavLink
                key={tab.path}
                to={tab.path}
                className={({ isActive }) =>
                  `relative whitespace-nowrap pb-2.5 text-xs font-medium transition ${
                    isActive
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {tab.label}

                    {isActive && (
                      <span className="absolute bottom-0 left-0 h-0.5 w-full rounded-full bg-blue-500" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      {/* Dashboard content */}
      <div className="mx-auto max-w-[1600px] px-5 py-3">
        <Outlet />
      </div>
    </div>
  );
}

export default Dashboard;