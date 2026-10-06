import { useState } from "react";
import {
  User,
  Building2,
  Settings,
  LogOut,
  ChevronDown,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

function UserMenu() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const handleAccountSettings = () => {
    setOpen(false);
    navigate("/settings");
  };

  const handleProfile = () => {
    setOpen(false);
    // Profile page can be implemented later
    navigate("/settings");
  };

  const handleOrganization = () => {
    setOpen(false);
    navigate("/admin");
  };

  const handleLogout = () => {
    setOpen(false);

    // Logout functionality can be connected
    // to the backend/auth system later.
    console.log("Logout clicked");
  };

  return (
    <div className="relative">

      {/* ================================================= */}
      {/* PROFILE BUTTON */}
      {/* ================================================= */}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-9 items-center gap-2 rounded-lg px-2 transition hover:bg-slate-100 dark:hover:bg-zinc-900"
        aria-expanded={open}
        aria-haspopup="menu"
      >

        {/* Avatar */}

        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-[11px] font-semibold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
          PN
        </div>

        {/* User name */}

        <div className="hidden text-left lg:block">

          <p className="text-[11px] font-semibold leading-none text-slate-800 dark:text-zinc-200">
            Priya Nair
          </p>

          <p className="mt-1 text-[9px] leading-none text-slate-400 dark:text-zinc-600">
            Admin
          </p>

        </div>

        <ChevronDown
          size={14}
          className={[
            "hidden text-slate-400 transition-transform lg:block",
            open ? "rotate-180" : "",
          ].join(" ")}
        />

      </button>


      {/* ================================================= */}
      {/* DROPDOWN */}
      {/* ================================================= */}

      {open && (
        <>
          {/* Optional backdrop */}

          <button
            type="button"
            aria-label="Close menu"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />

          <div
            className="absolute right-0 top-[46px] z-50 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl shadow-slate-900/10 dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-black/30"
            role="menu"
          >

            {/* ================================================= */}
            {/* PROFILE HEADER */}
            {/* ================================================= */}

            <div className="border-b border-slate-100 px-4 py-4 dark:border-zinc-800">

              <div className="flex items-center gap-3">

                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  PN
                </div>

                <div className="min-w-0">

                  <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">
                    Priya Nair
                  </p>

                  <p className="mt-0.5 truncate text-[10px] text-slate-500 dark:text-zinc-500">
                    priya@acmecorp.com
                  </p>

                </div>

              </div>

            </div>


            {/* ================================================= */}
            {/* MENU ITEMS */}
            {/* ================================================= */}

            <div className="p-1.5">

              {/* My Profile */}

              <button
                type="button"
                onClick={handleProfile}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
                role="menuitem"
              >

                <User
                  size={16}
                  strokeWidth={1.8}
                />

                <span>My Profile</span>

              </button>


              {/* Organization */}

              <button
                type="button"
                onClick={handleOrganization}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
                role="menuitem"
              >

                <Building2
                  size={16}
                  strokeWidth={1.8}
                />

                <span>Organization</span>

              </button>


              {/* Account Settings */}

              <button
                type="button"
                onClick={handleAccountSettings}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
                role="menuitem"
              >

                <Settings
                  size={16}
                  strokeWidth={1.8}
                />

                <span>Account Settings</span>

              </button>

            </div>


            {/* ================================================= */}
            {/* LOGOUT */}
            {/* ================================================= */}

            <div className="border-t border-slate-100 p-1.5 dark:border-zinc-800">

              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-xs text-red-500 transition hover:bg-red-50 dark:hover:bg-red-500/10"
                role="menuitem"
              >

                <LogOut
                  size={16}
                  strokeWidth={1.8}
                />

                <span>Sign Out</span>

              </button>

            </div>

          </div>
        </>
      )}

    </div>
  );
}

export default UserMenu;