import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarDays,
  CheckCircle2,
  Code2,
  GitBranch,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
  Zap,
} from "lucide-react";

import { useNavigate } from "react-router-dom";
import dashboardData from "../data/dashboardData";

function Home() {
  const navigate = useNavigate();
  const data = dashboardData;

  /*
   * =========================================================
   * ORGANIZATION CONNECTION STATE
   * =========================================================
   *
   * If organization is null / undefined, Home will show
   * the "Connect Salesforce Org" state.
   */

  const isConnected =
    data.organization &&
    data.organization.name &&
    data.organization.status === "Connected";

  return (
    <main className="min-h-[calc(100vh-68px)] bg-slate-50 dark:bg-zinc-950">
      <div className="mx-auto max-w-[1540px] space-y-3 px-4 py-4 sm:px-5 lg:px-6">

        {/* =====================================================
            HERO
        ===================================================== */}

        <section className="relative min-h-[238px] overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">

          {/* Background decoration */}

          <div className="absolute inset-0 overflow-hidden">

            <div className="absolute -right-20 -top-32 h-[360px] w-[650px] rounded-full bg-blue-50 blur-3xl dark:bg-blue-500/5" />

            <div className="absolute right-[270px] top-[80px] h-[180px] w-[300px] rounded-full bg-indigo-50/70 blur-3xl dark:bg-indigo-500/5" />

          </div>

          <div className="relative flex h-full min-h-[238px] items-center">

            {/* Hero text */}

            <div className="z-10 w-full px-6 py-7 sm:px-8 lg:w-[58%] lg:px-9">

              <div className="flex items-center gap-2">

                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  <Sparkles size={14} />
                </div>

                <span className="text-[9px] font-semibold uppercase tracking-[0.1em] text-blue-600 dark:text-blue-400">
                  Salesforce Intelligence Platform
                </span>

              </div>

              <h1 className="mt-3 text-[30px] font-bold leading-tight tracking-tight text-slate-950 dark:text-white sm:text-[34px]">
                Good morning, Priya! <span>👋</span>
              </h1>

              <p className="mt-2 max-w-[620px] text-[13px] leading-5 text-slate-500 dark:text-zinc-400">
                ApexAI is your AI-powered command center for Salesforce.
                Build smarter, operate faster and optimize your organization.
              </p>

              <div className="mt-5 flex items-center gap-3">

                <button
                  type="button"
                  onClick={() => navigate("/workspace")}
                  className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-[11px] font-semibold text-white shadow-sm transition hover:bg-blue-700"
                >
                  <Sparkles size={14} />
                  Open AI Workspace
                  <ArrowRight size={13} />
                </button>

                <button
                  type="button"
                  onClick={() => navigate("/dashboard/overview")}
                  className="inline-flex h-10 items-center gap-2 rounded-lg border border-blue-200 bg-white px-4 text-[11px] font-semibold text-blue-600 transition hover:bg-blue-50 dark:border-blue-500/20 dark:bg-zinc-950 dark:text-blue-400"
                >
                  View Intelligence
                  <ArrowRight size={13} />
                </button>

              </div>

            </div>

            {/* Hero illustration */}

            <div className="absolute right-4 top-1/2 hidden h-[210px] w-[480px] -translate-y-1/2 lg:block">

              {/* Cloud */}

              <div className="absolute left-[65px] top-[45px] flex h-14 w-20 items-center justify-center rounded-full bg-blue-100/80 text-blue-500 dark:bg-blue-500/10">

                <div className="relative">

                  <div className="h-7 w-11 rounded-full bg-blue-400/80" />

                  <div className="absolute -left-2 bottom-0 h-5 w-5 rounded-full bg-blue-400/80" />

                  <div className="absolute -right-1 bottom-0 h-6 w-6 rounded-full bg-blue-400/80" />

                </div>

              </div>

              {/* Dotted connector */}

              <div className="absolute left-[125px] top-[104px] h-[1px] w-[115px] rotate-[12deg] border-t border-dashed border-blue-300 dark:border-blue-500/20" />

              {/* Dashboard window */}

              <div className="absolute left-[175px] top-[18px] h-[145px] w-[225px] rotate-[3deg] rounded-xl border border-blue-200 bg-white p-3 shadow-xl shadow-blue-100/60 dark:border-blue-500/20 dark:bg-zinc-900 dark:shadow-none">

                <div className="flex items-center justify-between">

                  <div className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-blue-200" />
                    <span className="h-2 w-2 rounded-full bg-blue-200" />
                    <span className="h-2 w-2 rounded-full bg-blue-200" />
                  </div>

                  <div className="h-2 w-14 rounded bg-blue-50 dark:bg-blue-500/10" />

                </div>

                <div className="mt-4 flex items-end gap-3">

                  <div className="h-16 w-[115px] rounded-md bg-blue-50 p-2 dark:bg-blue-500/10">

                    <div className="flex h-full items-end gap-2">
                      <span className="h-5 w-3 rounded-sm bg-blue-300" />
                      <span className="h-8 w-3 rounded-sm bg-blue-400" />
                      <span className="h-11 w-3 rounded-sm bg-blue-500" />
                      <span className="h-7 w-3 rounded-sm bg-blue-300" />
                      <span className="h-13 w-3 rounded-sm bg-blue-400" />
                    </div>

                  </div>

                  <div className="relative h-16 w-16 rounded-full border-[8px] border-blue-100 dark:border-blue-500/10">
                    <div className="absolute inset-0 rounded-full border-[8px] border-transparent border-t-blue-500 border-r-blue-500" />
                  </div>

                </div>

              </div>

              {/* Database */}

              <div className="absolute right-[20px] bottom-[18px] h-[70px] w-[70px]">

                <div className="absolute top-0 h-5 w-[70px] rounded-[50%] bg-blue-500" />

                <div className="absolute top-2 h-12 w-[70px] rounded-b-lg bg-blue-500" />

                <div className="absolute top-[14px] h-4 w-[70px] rounded-[50%] border-2 border-blue-300 bg-blue-500" />

                <div className="absolute top-[32px] h-4 w-[70px] rounded-[50%] border-2 border-blue-300 bg-blue-500" />

              </div>

            </div>

          </div>

        </section>


        {/* =====================================================
            SALESFORCE ENVIRONMENT
        ===================================================== */}

        <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">

          {isConnected ? (

            /* =================================================
               CONNECTED STATE
            ================================================= */

            <div className="flex min-h-[78px] items-center justify-between">

              <div className="flex items-center gap-3 px-5">

                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  <Building2 size={18} />
                </div>

                <div>

                  <p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-blue-600">
                    Connected Environment
                  </p>

                  <div className="mt-0.5 flex items-center gap-2">

                    <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                      {data.organization.name}
                    </h2>

                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[8px] font-semibold text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">

                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />

                      Connected

                    </span>

                  </div>

                  <p className="text-[9px] text-slate-400 dark:text-zinc-600">
                    {data.organization.environment}
                    {" · "}
                    Salesforce API {data.organization.apiVersion}
                  </p>

                </div>

              </div>

              <div className="flex h-full items-center border-l border-slate-100 dark:border-zinc-800">

                <div className="hidden items-center gap-3 px-6 md:flex">

                  <CalendarDays
                    size={18}
                    className="text-slate-400"
                  />

                  <div>

                    <p className="text-[8px] font-semibold uppercase tracking-wide text-slate-400">
                      Last synchronized
                    </p>

                    <p className="mt-1 text-[9px] text-slate-500 dark:text-zinc-500">
                      {data.sync?.lastSynced || "Not synchronized"}
                    </p>

                  </div>

                </div>

                <button
                  type="button"
                  onClick={() => navigate("/dashboard/overview")}
                  className="mr-5 inline-flex items-center gap-2 rounded-lg border border-blue-200 px-3.5 py-2 text-[10px] font-semibold text-blue-600 transition hover:bg-blue-50 dark:border-blue-500/20 dark:text-blue-400"
                >
                  Open Intelligence
                  <ArrowRight size={12} />
                </button>

              </div>

            </div>

          ) : (

            /* =================================================
               NOT CONNECTED STATE
            ================================================= */

            <div className="flex min-h-[110px] flex-col justify-center gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">

              <div className="flex items-center gap-3">

                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  <Building2 size={18} />
                </div>

                <div>

                  <p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-blue-600">
                    Salesforce Environment
                  </p>

                  <h2 className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                    No Salesforce organization connected
                  </h2>

                  <p className="mt-1 max-w-[650px] text-[9px] text-slate-500 dark:text-zinc-500">
                    Connect a Salesforce organization to unlock
                    intelligence, AI workspace, data operations and
                    migration.
                  </p>

                </div>

              </div>

              <button
                type="button"
                onClick={() => navigate("/settings")}
                className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-[10px] font-semibold text-white shadow-sm transition hover:bg-blue-700"
              >
                <ShieldCheck size={14} />
                Connect Salesforce Org
                <ArrowRight size={12} />
              </button>

            </div>

          )}

        </section>


        {/* =====================================================
            ACTIONS + RECENT ACTIVITY
        ===================================================== */}

        <section className="grid grid-cols-1 gap-3 lg:grid-cols-[1.25fr_0.75fr]">

          {/* ===================================================
              WHAT DO YOU WANT TO DO
          =================================================== */}

          <section className="rounded-xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">

            <div>

              <p className="px-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-700 dark:text-zinc-300">
                What do you want to do?
              </p>

              <p className="mt-1 px-1 text-[9px] text-slate-400 dark:text-zinc-600">
                Start an ApexAI workflow
              </p>

            </div>

            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">

              <ActionCard
                primary
                icon={Sparkles}
                title="AI Workspace"
                description="Describe what you want to build and let ApexAI create a complete implementation plan."
                action="Open workspace"
                onClick={() => navigate("/workspace")}
              />

              <ActionCard
                icon={Upload}
                title="Import Data"
                description="Import records into Salesforce and map your source fields with confidence."
                action="Start import"
                onClick={() => navigate("/import")}
                green
              />

              <ActionCard
                icon={GitBranch}
                title="Migrate Org"
                description="Move Salesforce metadata between connected organizations."
                action="Start migration"
                onClick={() => navigate("/migration")}
                purple
              />

              <ActionCard
                icon={BarChart3}
                title="Inspect Org"
                description="Analyze organization health, limits, users and metadata with intelligence."
                action="Open intelligence"
                onClick={() => navigate("/dashboard/overview")}
              />

            </div>

          </section>


          {/* ===================================================
              RECENT ACTIVITY
          =================================================== */}

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">

            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 dark:border-zinc-800">

              <div>

                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-700 dark:text-zinc-300">
                  Recent Activity
                </p>

                <p className="mt-0.5 text-[8px] text-slate-400 dark:text-zinc-600">
                  Latest organization events
                </p>

              </div>

              {isConnected && (
                <button
                  type="button"
                  onClick={() => navigate("/dashboard/overview")}
                  className="inline-flex items-center gap-1 text-[9px] font-semibold text-blue-600"
                >
                  View all
                  <ArrowRight size={10} />
                </button>
              )}

            </div>


            <div className="divide-y divide-slate-100 dark:divide-zinc-800">

              {isConnected ? (

                data.recentActivity?.length > 0 ? (

                  data.recentActivity.map((item) => (
                    <ActivityRow
                      key={item.id}
                      item={item}
                    />
                  ))

                ) : (

                  <EmptyActivityState />

                )

              ) : (

                <div className="flex min-h-[260px] items-center justify-center px-5">

                  <div className="text-center">

                    <Building2
                      size={22}
                      className="mx-auto text-slate-300 dark:text-zinc-700"
                    />

                    <p className="mt-2 text-[10px] font-medium text-slate-500 dark:text-zinc-500">
                      Connect a Salesforce organization to view activity.
                    </p>

                    <button
                      type="button"
                      onClick={() => navigate("/settings")}
                      className="mt-2 text-[9px] font-semibold text-blue-600"
                    >
                      Connect organization →
                    </button>

                  </div>

                </div>

              )}

            </div>

          </section>

        </section>

      </div>
    </main>
  );
}


/* =========================================================
   EMPTY ACTIVITY STATE
========================================================= */

function EmptyActivityState() {
  return (
    <div className="flex min-h-[90px] items-center justify-center">

      <div className="text-center">

        <CheckCircle2
          size={20}
          className="mx-auto text-slate-300 dark:text-zinc-700"
        />

        <p className="mt-2 text-[9px] text-slate-500 dark:text-zinc-500">
          No recent activity
        </p>

      </div>

    </div>
  );
}


/* =========================================================
   ACTION CARD
========================================================= */

function ActionCard({
  icon: Icon,
  title,
  description,
  action,
  onClick,
  primary = false,
  green = false,
  purple = false,
}) {
  let iconStyle =
    "bg-blue-50 text-blue-500 dark:bg-blue-500/10";

  let actionStyle = "text-blue-500";

  if (green) {
    iconStyle =
      "bg-emerald-50 text-emerald-500 dark:bg-emerald-500/10";

    actionStyle = "text-emerald-500";
  }

  if (purple) {
    iconStyle =
      "bg-purple-50 text-purple-500 dark:bg-purple-500/10";

    actionStyle = "text-purple-500";
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "group relative flex min-h-[145px] flex-col rounded-xl border p-3.5 text-left transition-all",

        primary
          ? "border-blue-600 bg-gradient-to-br from-blue-600 to-blue-700 shadow-md shadow-blue-500/10 hover:from-blue-700 hover:to-blue-800"
          : "border-slate-200 bg-white hover:border-blue-200 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-blue-500/20",
      ].join(" ")}
    >

      {/* Icon + Arrow */}

      <div className="flex items-start justify-between">

        <div
          className={[
            "flex h-9 w-9 items-center justify-center rounded-lg",

            primary
              ? "bg-white/15 text-white"
              : iconStyle,
          ].join(" ")}
        >
          <Icon
            size={17}
            strokeWidth={1.8}
          />
        </div>

        <ArrowUpRight
          size={13}
          strokeWidth={1.7}
          className={
            primary
              ? "text-white/60 transition group-hover:text-white"
              : "text-slate-300 transition group-hover:text-blue-500 dark:text-zinc-700"
          }
        />

      </div>


      {/* Title */}

      <h3
        className={[
          "mt-3 text-[13px] font-semibold",

          primary
            ? "text-white"
            : "text-slate-900 dark:text-white",
        ].join(" ")}
      >
        {title}
      </h3>


      {/* Description */}

      <p
        className={[
          "mt-2 max-w-[260px] text-[9px] leading-[15px]",

          primary
            ? "text-blue-100"
            : "text-slate-500 dark:text-zinc-500",
        ].join(" ")}
      >
        {description}
      </p>


      {/* Action */}

      <div
        className={[
          "mt-auto flex items-center gap-1 pt-3 text-[9px] font-semibold",

          primary
            ? "text-white"
            : actionStyle,
        ].join(" ")}
      >

        <span>{action}</span>

        <ArrowRight
          size={10}
          strokeWidth={2}
        />

      </div>

    </button>
  );
}


/* =========================================================
   ACTIVITY ROW
========================================================= */

function ActivityRow({ item }) {
  const icons = {
    deployment: Code2,
    migration: GitBranch,
    import: Upload,
    warning: Zap,
    user: Users,
  };

  const Icon =
    icons[item.type] || CheckCircle2;

  return (
    <div className="flex items-center gap-2.5 px-4 py-3">

      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-blue-500 dark:bg-zinc-900">

        <Icon size={13} />

      </div>

      <div className="min-w-0 flex-1">

        <p className="truncate text-[9px] font-medium text-slate-800 dark:text-zinc-300">
          {item.title}
        </p>

        <p className="mt-0.5 text-[8px] text-slate-400 dark:text-zinc-600">
          {item.user}
        </p>

      </div>

      <span className="shrink-0 text-[8px] text-slate-400 dark:text-zinc-600">
        {item.time}
      </span>

    </div>
  );
}


export default Home;