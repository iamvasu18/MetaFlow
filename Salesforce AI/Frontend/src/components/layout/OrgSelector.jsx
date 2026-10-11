import { useState, useRef, useEffect } from "react";
import {
  Building2,
  Check,
  ChevronDown,
  Cloud,
} from "lucide-react";

import { useOrg } from "../../context/OrgContext";

function OrgSelector() {
  const [open, setOpen] = useState(false);

  const {
    organizations,
    activeOrg,
    selectOrganization,
  } = useOrg();

  const selectorRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (
        selectorRef.current &&
        !selectorRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    }

    document.addEventListener(
      "mousedown",
      handleClickOutside
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleClickOutside
      );
    };
  }, []);

  function handleSelect(org) {
    selectOrganization(org.id);
    setOpen(false);
  }

  return (
    <div
      ref={selectorRef}
      className="relative"
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-500 dark:bg-blue-500/10">
          <Cloud size={15} />
        </div>

        <div className="hidden text-left md:block">
          <p className="max-w-[150px] truncate text-[11px] font-semibold text-slate-800 dark:text-zinc-100">
            {activeOrg && /^00D[A-Za-z0-9]+$/.test(activeOrg.name || "") ? activeOrg.username : activeOrg?.name || "No organization"}
          </p>

          <p className="text-[9px] text-slate-400 dark:text-zinc-500">
            {activeOrg?.type || "Not connected"}
          </p>
        </div>

        <ChevronDown
          size={14}
          className={`text-slate-400 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
          <div className="border-b border-slate-100 px-4 py-3 dark:border-zinc-800">
            <p className="text-xs font-semibold text-slate-900 dark:text-white">
              Salesforce Organizations
            </p>

            <p className="mt-0.5 text-[10px] text-slate-400">
              Select the organization you want to work with.
            </p>
          </div>

          <div className="p-1.5">
            <a href="/settings#salesforce" className="block p-3 text-xs text-blue-600">Connect a Salesforce org</a>
            {organizations.map((org) => {
              const isSelected =
                activeOrg?.id === org.id;

              return (
                <button
                  key={org.id}
                  type="button"
                  onClick={() => handleSelect(org)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition ${
                    isSelected
                      ? "bg-blue-50 dark:bg-blue-500/10"
                      : "hover:bg-slate-50 dark:hover:bg-zinc-900"
                  }`}
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-zinc-900 dark:text-zinc-400">
                    <Building2 size={15} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-800 dark:text-zinc-200">
                      {/^00D[A-Za-z0-9]+$/.test(org.name || "") ? org.username : org.name}
                    </p>

                    <div className="mt-0.5 flex items-center gap-2">
                      <span className="text-[9px] text-slate-400">
                        {org.type}
                      </span>

                      <span className="flex items-center gap-1 text-[9px] text-slate-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                        {org.status}
                      </span>
                    </div>
                  </div>

                  {isSelected && (
                    <Check
                      size={15}
                      className="text-blue-500"
                    />
                  )}
                </button>
              );
            })}
          </div>

          <p className="border-t border-slate-100 p-3 text-[10px] text-slate-400 dark:border-zinc-800">
            Connections authorized through Salesforce OAuth.
          </p>
        </div>
      )}
    </div>
  );
}

export default OrgSelector;