import {
  ArrowLeftRight,
  Home,
  LayoutDashboard,
  Moon,
  Shield,
  Sparkles,
  Sun,
  Upload,
} from "lucide-react";

import { NavLink } from "react-router-dom";

import { useTheme } from "../../context/ThemeContext";
import UserMenu from "./UserMenu";
import OrgSelector from "./OrgSelector";

const navItems = [
  {
    label: "Home",
    path: "/",
    icon: Home,
  },
  {
    label: "AI Workspace",
    path: "/workspace",
    icon: Sparkles,
  },
  {
    label: "Intelligence",
    path: "/dashboard/overview",
    icon: LayoutDashboard,
  },
  {
    label: "Import",
    path: "/import",
    icon: Upload,
  },
  {
    label: "Migration",
    path: "/migration",
    icon: ArrowLeftRight,
  },
  {
    label: "Admin",
    path: "/admin",
    icon: Shield,
  },
];

function TopNavbar() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl dark:border-zinc-800/80 dark:bg-zinc-950/90">

      <div className="flex h-[64px] items-center px-4 lg:px-6">

        {/* ================================================= */}
        {/* BRAND */}
        {/* ================================================= */}

        <NavLink
          to="/"
          className="mr-5 flex shrink-0 items-center gap-2.5"
        >
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500 text-white shadow-sm shadow-blue-500/20">

            <Sparkles
              size={18}
              strokeWidth={2}
            />

          </div>

          <div className="hidden leading-none sm:block">

            <p className="text-[17px] font-bold tracking-tight text-slate-950 dark:text-white">
              Apex<span className="text-blue-500">AI</span>
            </p>

            <p className="mt-1 text-[7px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-zinc-600">
              Salesforce Intelligence
            </p>

          </div>
        </NavLink>

        {/* ================================================= */}
        {/* PRIMARY NAVIGATION */}
        {/* ================================================= */}

        <nav className="flex h-full min-w-0 items-center gap-0.5 overflow-x-auto">

          {navItems.map((item) => (
            <NavigationItem
              key={item.path}
              item={item}
            />
          ))}

        </nav>

        {/* ================================================= */}
        {/* RIGHT SIDE */}
        {/* ================================================= */}

        <div className="ml-auto flex shrink-0 items-center gap-1.5">

          {/* Divider */}

          <div className="mx-1 hidden h-6 w-px bg-slate-200 lg:block dark:bg-zinc-800" />

          {/* Salesforce Organization */}

          <OrgSelector />

          {/* Theme */}

          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            title={
              theme === "dark"
                ? "Switch to light mode"
                : "Switch to dark mode"
            }
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white"
          >
            {theme === "dark" ? (
              <Sun
                size={16}
                strokeWidth={1.8}
              />
            ) : (
              <Moon
                size={16}
                strokeWidth={1.8}
              />
            )}
          </button>

          {/* User */}

          <UserMenu />

        </div>

      </div>
    </header>
  );
}

/* ========================================================= */
/* NAVIGATION ITEM */
/* ========================================================= */

function NavigationItem({ item }) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      className={({ isActive }) =>
        [
          "group relative flex h-9 shrink-0 items-center gap-2 rounded-lg px-2.5 text-[11px] font-medium transition-all",

          isActive
            ? "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white",
        ].join(" ")
      }
    >
      <Icon
        size={15}
        strokeWidth={1.8}
        className="shrink-0"
      />

      <span className="hidden md:inline">
        {item.label}
      </span>
    </NavLink>
  );
}

export default TopNavbar;