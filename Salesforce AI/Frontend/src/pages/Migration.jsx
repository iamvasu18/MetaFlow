import { useMemo, useState } from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Database,
  FileCode2,
  GitBranch,
  Loader2,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  X,
  AlertTriangle,
} from "lucide-react";

const OBJECTS = [
  {
    name: "Account",
    apiName: "Account",
    records: "1,284",
    type: "Standard",
    dependencies: [],
  },
  {
    name: "Contact",
    apiName: "Contact",
    records: "3,842",
    type: "Standard",
    dependencies: ["Account"],
  },
  {
    name: "Opportunity",
    apiName: "Opportunity",
    records: "2,416",
    type: "Standard",
    dependencies: ["Account"],
  },
  {
    name: "Opportunity Product",
    apiName: "OpportunityLineItem",
    records: "4,238",
    type: "Standard",
    dependencies: ["Opportunity", "Product"],
  },
  {
    name: "Case",
    apiName: "Case",
    records: "1,105",
    type: "Standard",
    dependencies: ["Account", "Contact"],
  },
  {
    name: "Lead",
    apiName: "Lead",
    records: "865",
    type: "Standard",
    dependencies: [],
  },
  {
    name: "Product",
    apiName: "Product2",
    records: "284",
    type: "Standard",
    dependencies: [],
  },
  {
    name: "Campaign",
    apiName: "Campaign",
    records: "92",
    type: "Standard",
    dependencies: [],
  },
  {
    name: "Custom Object",
    apiName: "Project__c",
    records: "648",
    type: "Custom",
    dependencies: ["Account"],
  },
];

const STEPS = [
  "Source Org",
  "Select Objects",
  "Review Plan",
  "Approve",
  "Execute",
  "Results",
];

function Migration() {
  const [currentStep, setCurrentStep] = useState(1);

  const [sourceOrg, setSourceOrg] = useState({
    name: "Acme Corp Production",
    environment: "Production",
    apiVersion: "v60.0",
  });

  const [targetOrg, setTargetOrg] = useState({
    name: "Acme UAT",
    environment: "UAT",
    apiVersion: "v60.0",
  });

  const [migrationName, setMigrationName] = useState(
    "Production → UAT Migration"
  );

  const [selectedObjects, setSelectedObjects] = useState([
    "Account",
    "Contact",
  ]);

  const [search, setSearch] = useState("");

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState(0);
  const [approved, setApproved] = useState(false);

  const filteredObjects = useMemo(() => {
    const query = search.toLowerCase().trim();

    if (!query) return OBJECTS;

    return OBJECTS.filter(
      (object) =>
        object.name.toLowerCase().includes(query) ||
        object.apiName.toLowerCase().includes(query)
    );
  }, [search]);

  const selectedData = OBJECTS.filter((object) =>
    selectedObjects.includes(object.name)
  );

  const totalRecords = selectedData.reduce(
    (total, object) =>
      total + Number(object.records.replace(",", "")),
    0
  );

  const dependencyCount = selectedData.reduce(
    (total, object) => total + object.dependencies.length,
    0
  );

  const toggleObject = (objectName) => {
    setSelectedObjects((current) =>
      current.includes(objectName)
        ? current.filter((name) => name !== objectName)
        : [...current, objectName]
    );
  };

  const selectAll = () => {
    setSelectedObjects(OBJECTS.map((object) => object.name));
  };

  const clearAll = () => {
    setSelectedObjects([]);
  };

  const handleAnalyze = () => {
    if (!selectedObjects.length) return;

    setIsAnalyzing(true);

    setTimeout(() => {
      setIsAnalyzing(false);
      setCurrentStep(2);
    }, 900);
  };

  const handleApprove = () => {
    setApproved(true);
    setCurrentStep(4);
  };

  const handleExecute = () => {
    setIsExecuting(true);
    setCurrentStep(4);
    setExecutionProgress(0);

    let progress = 0;

    const interval = setInterval(() => {
      progress += 10;
      setExecutionProgress(progress);

      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          setIsExecuting(false);
          setCurrentStep(5);
        }, 500);
      }
    }, 250);
  };

  const handleStartOver = () => {
    setCurrentStep(1);
    setSelectedObjects(["Account", "Contact"]);
    setMigrationName("Production → UAT Migration");
    setApproved(false);
    setIsExecuting(false);
    setExecutionProgress(0);
  };

  return (
    <main className="min-h-[calc(100vh-68px)] bg-slate-50 px-4 py-5 dark:bg-zinc-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1180px]">

        {/* ================================================= */}
        {/* PAGE HEADER */}
        {/* ================================================= */}

        <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                <ArrowLeftRight size={18} />
              </div>

              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-blue-600 dark:text-blue-400">
                Salesforce Migration
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
              Org-to-Org Migration
            </h1>

            <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">
              Move Salesforce metadata and data between connected
              organizations with dependency-aware ordering.
            </p>
          </div>

          <button
            type="button"
            onClick={handleStartOver}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:text-white"
          >
            <RotateCcw size={14} />
            Start Over
          </button>
        </div>

        {/* ================================================= */}
        {/* STEPPER */}
        {/* ================================================= */}

        <div className="mb-6 overflow-x-auto rounded-xl border border-slate-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex min-w-[760px] items-center">
            {STEPS.map((step, index) => {
              const completed = index < currentStep;
              const active = index === currentStep;

              return (
                <div
                  key={step}
                  className="flex flex-1 items-center"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={[
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                        completed
                          ? "bg-blue-600 text-white"
                          : active
                          ? "border-2 border-blue-500 bg-blue-50 text-blue-600 dark:bg-blue-500/10"
                          : "bg-slate-100 text-slate-400 dark:bg-zinc-800 dark:text-zinc-500",
                      ].join(" ")}
                    >
                      {completed ? (
                        <Check size={14} />
                      ) : (
                        index + 1
                      )}
                    </div>

                    <span
                      className={[
                        "whitespace-nowrap text-xs font-medium",
                        active || completed
                          ? "text-slate-900 dark:text-white"
                          : "text-slate-400 dark:text-zinc-600",
                      ].join(" ")}
                    >
                      {step}
                    </span>
                  </div>

                  {index !== STEPS.length - 1 && (
                    <div
                      className={[
                        "mx-3 h-px flex-1",
                        index < currentStep
                          ? "bg-blue-500"
                          : "bg-slate-200 dark:bg-zinc-800",
                      ].join(" ")}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ================================================= */}
        {/* SOURCE / TARGET */}
        {/* ================================================= */}

        <div className="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto_1fr]">

          <OrgCard
            label="SOURCE ORGANIZATION"
            icon={Database}
            org={sourceOrg}
            variant="source"
            onChange={(value) =>
              setSourceOrg((current) => ({
                ...current,
                name: value,
              }))
            }
          />

          <div className="hidden items-center justify-center lg:flex">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-blue-500 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <ArrowRight size={17} />
            </div>
          </div>

          <OrgCard
            label="TARGET ORGANIZATION"
            icon={Target}
            org={targetOrg}
            variant="target"
            onChange={(value) =>
              setTargetOrg((current) => ({
                ...current,
                name: value,
              }))
            }
          />

        </div>

        {/* ================================================= */}
        {/* STEP 1 */}
        {/* ================================================= */}

        {currentStep === 1 && (
          <>
            {/* Migration Name */}

            <section className="mb-5 rounded-xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <SectionHeader
                title="Migration Details"
                description="Give this migration a name so it can be tracked later."
              />

              <label className="mt-4 block">
                <span className="mb-2 block text-xs font-semibold text-slate-700 dark:text-zinc-300">
                  Migration Name
                </span>

                <input
                  value={migrationName}
                  onChange={(event) =>
                    setMigrationName(event.target.value)
                  }
                  className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200 dark:focus:border-blue-500 dark:focus:bg-zinc-900"
                  placeholder="Enter migration name..."
                />
              </label>
            </section>

            {/* Select Objects */}

            <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">

              <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                      Select Objects to Migrate
                    </h2>

                    <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
                      Select the Salesforce objects you want to move.
                    </p>
                  </div>

                  <div className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                    {selectedObjects.length} selected
                  </div>
                </div>

                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <div className="relative flex-1">
                    <Search
                      size={15}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                      value={search}
                      onChange={(event) =>
                        setSearch(event.target.value)
                      }
                      placeholder="Search objects..."
                      className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs text-slate-700 outline-none transition focus:border-blue-400 focus:bg-white dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200"
                    />
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={selectAll}
                      className="rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      Select all
                    </button>

                    <button
                      type="button"
                      onClick={clearAll}
                      className="rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      Clear
                    </button>
                  </div>
                </div>
              </div>

              <div className="divide-y divide-slate-100 dark:divide-zinc-800">
                {filteredObjects.map((object) => {
                  const selected = selectedObjects.includes(
                    object.name
                  );

                  return (
                    <button
                      key={object.apiName}
                      type="button"
                      onClick={() =>
                        toggleObject(object.name)
                      }
                      className={[
                        "flex w-full items-center gap-4 px-5 py-3.5 text-left transition",
                        selected
                          ? "bg-blue-50/50 dark:bg-blue-500/5"
                          : "hover:bg-slate-50 dark:hover:bg-zinc-800/50",
                      ].join(" ")}
                    >
                      <div
                        className={[
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded border",
                          selected
                            ? "border-blue-600 bg-blue-600 text-white"
                            : "border-slate-300 bg-white dark:border-zinc-700 dark:bg-zinc-900",
                        ].join(" ")}
                      >
                        {selected && <Check size={13} />}
                      </div>

                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-blue-500 dark:bg-zinc-800">
                        <Database size={16} />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                            {object.name}
                          </p>

                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[9px] text-slate-500 dark:bg-zinc-800 dark:text-zinc-500">
                            {object.apiName}
                          </span>
                        </div>

                        <p className="mt-0.5 text-[10px] text-slate-400 dark:text-zinc-600">
                          {object.type} object ·{" "}
                          {object.records} records
                        </p>
                      </div>

                      {object.dependencies.length > 0 && (
                        <div className="hidden items-center gap-1 text-[10px] text-slate-400 sm:flex">
                          <GitBranch size={12} />
                          {object.dependencies.length} dependencies
                        </div>
                      )}
                    </button>
                  );
                })}

                {!filteredObjects.length && (
                  <div className="px-5 py-12 text-center">
                    <Search
                      size={22}
                      className="mx-auto text-slate-300"
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      No objects found.
                    </p>
                  </div>
                )}
              </div>

              {/* Selection Summary */}

              <div className="flex flex-col gap-4 border-t border-slate-200 bg-slate-50/70 p-5 dark:border-zinc-800 dark:bg-zinc-950/50 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-700 dark:text-zinc-300">
                    {selectedObjects.length} objects selected
                  </p>

                  <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
                    Approximately{" "}
                    {totalRecords.toLocaleString()} records
                  </p>
                </div>

                <button
                  type="button"
                  disabled={
                    selectedObjects.length === 0 ||
                    isAnalyzing
                  }
                  onClick={handleAnalyze}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2
                        size={15}
                        className="animate-spin"
                      />
                      Analyzing dependencies...
                    </>
                  ) : (
                    <>
                      <Sparkles size={15} />
                      Analyze & Create Plan
                      <ArrowRight size={15} />
                    </>
                  )}
                </button>
              </div>
            </section>
          </>
        )}

        {/* ================================================= */}
        {/* STEP 2 - REVIEW */}
        {/* ================================================= */}

        {currentStep === 2 && (
          <ReviewPlan
            selectedData={selectedData}
            totalRecords={totalRecords}
            dependencyCount={dependencyCount}
            onBack={() => setCurrentStep(1)}
            onContinue={() => setCurrentStep(3)}
          />
        )}

        {/* ================================================= */}
        {/* STEP 3 - APPROVE */}
        {/* ================================================= */}

        {currentStep === 3 && (
          <ApprovalStep
            migrationName={migrationName}
            sourceOrg={sourceOrg}
            targetOrg={targetOrg}
            selectedData={selectedData}
            totalRecords={totalRecords}
            onBack={() => setCurrentStep(2)}
            onApprove={handleApprove}
          />
        )}

        {/* ================================================= */}
        {/* STEP 4 - EXECUTE */}
        {/* ================================================= */}

        {currentStep === 4 && (
          <ExecuteStep
            isExecuting={isExecuting}
            progress={executionProgress}
            selectedData={selectedData}
            onExecute={handleExecute}
          />
        )}

        {/* ================================================= */}
        {/* STEP 5 - RESULTS */}
        {/* ================================================= */}

        {currentStep === 5 && (
          <ResultsStep
            selectedData={selectedData}
            totalRecords={totalRecords}
            onStartOver={handleStartOver}
          />
        )}

        {/* ================================================= */}
        {/* FOOTER */}
        {/* ================================================= */}

        <div className="mt-5 flex items-center justify-between px-1 text-[10px] text-slate-400 dark:text-zinc-600">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            ApexAI migration engine ready
          </span>

          <span>
            Dependency-aware · Salesforce-native
          </span>
        </div>
      </div>
    </main>
  );
}

/* ========================================================= */
/* ORGANIZATION CARD */
/* ========================================================= */

function OrgCard({
  label,
  icon: Icon,
  org,
  variant,
  onChange,
}) {
  const isTarget = variant === "target";

  return (
    <div
      className={[
        "rounded-xl border bg-white p-4 dark:bg-zinc-900",
        isTarget
          ? "border-blue-200 dark:border-blue-500/20"
          : "border-emerald-200 dark:border-emerald-500/20",
      ].join(" ")}
    >
      <div className="flex items-center gap-3">
        <div
          className={[
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            isTarget
              ? "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400"
              : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
          ].join(" ")}
        >
          <Icon size={18} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-zinc-600">
            {label}
          </p>

          <div className="mt-1 flex flex-wrap items-center gap-2">
            <select
              value={org.name}
              onChange={(event) => onChange(event.target.value)}
              className="max-w-full bg-transparent text-sm font-semibold text-slate-900 outline-none dark:text-white"
            >
              {isTarget ? (
                <>
                  <option>Acme UAT</option>
                  <option>Acme Corp Sandbox</option>
                  <option>Acme Corp Staging</option>
                </>
              ) : (
                <>
                  <option>Acme Corp Production</option>
                  <option>Acme Corp Sandbox</option>
                </>
              )}
            </select>

            <span
              className={[
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold",
                isTarget
                  ? "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400"
                  : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
              ].join(" ")}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              Connected
            </span>
          </div>

          <p className="mt-1 text-[10px] text-slate-400 dark:text-zinc-600">
            {org.environment} · Salesforce API {org.apiVersion}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ========================================================= */
/* SECTION HEADER */
/* ========================================================= */

function SectionHeader({ title, description }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
        {title}
      </h2>

      {description && (
        <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
          {description}
        </p>
      )}
    </div>
  );
}

/* ========================================================= */
/* REVIEW PLAN */
/* ========================================================= */

function ReviewPlan({
  selectedData,
  totalRecords,
  dependencyCount,
  onBack,
  onContinue,
}) {
  return (
    <div className="space-y-5">

      <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
          <SectionHeader
            title="Migration Plan"
            description="ApexAI analyzed the selected objects and created a dependency-aware migration order."
          />
        </div>

        <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-3">
          <SummaryMetric
            label="Objects"
            value={selectedData.length}
            icon={Database}
          />

          <SummaryMetric
            label="Estimated Records"
            value={totalRecords.toLocaleString()}
            icon={FileCode2}
          />

          <SummaryMetric
            label="Dependencies"
            value={dependencyCount}
            icon={GitBranch}
          />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">

        <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                Recommended Migration Order
              </h2>

              <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
                Parent objects are migrated before dependent records.
              </p>
            </div>

            <span className="hidden rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold text-emerald-600 sm:block dark:bg-emerald-500/10 dark:text-emerald-400">
              Dependency checked
            </span>
          </div>
        </div>

        <div className="p-5">
          <div className="space-y-2">
            {selectedData.map((object, index) => (
              <div
                key={object.apiName}
                className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50/70 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950/50"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-50 text-[10px] font-bold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  {index + 1}
                </div>

                <Database
                  size={15}
                  className="text-blue-500"
                />

                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                    {object.name}
                  </p>

                  <p className="text-[10px] text-slate-400 dark:text-zinc-600">
                    {object.apiName} · {object.records} records
                  </p>
                </div>

                {object.dependencies.length > 0 && (
                  <span className="hidden text-[10px] text-slate-400 sm:block">
                    Depends on {object.dependencies.join(", ")}
                  </span>
                )}

                <CheckCircle2
                  size={15}
                  className="text-emerald-500"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50/70 p-5 sm:flex-row sm:justify-between dark:border-zinc-800 dark:bg-zinc-950/50">
          <button
            type="button"
            onClick={onBack}
            className="h-10 rounded-lg border border-slate-200 bg-white px-4 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
          >
            Back
          </button>

          <button
            type="button"
            onClick={onContinue}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white hover:bg-blue-700"
          >
            Continue to Approval
            <ArrowRight size={15} />
          </button>
        </div>
      </section>

    </div>
  );
}

/* ========================================================= */
/* APPROVAL */
/* ========================================================= */

function ApprovalStep({
  migrationName,
  sourceOrg,
  targetOrg,
  selectedData,
  totalRecords,
  onBack,
  onApprove,
}) {
  const [confirmed, setConfirmed] = useState(false);

  return (
    <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">

      <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
        <SectionHeader
          title="Approve Migration"
          description="Review the migration details before execution."
        />
      </div>

      <div className="space-y-5 p-5">

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <InfoBox
            label="Migration"
            value={migrationName}
          />

          <InfoBox
            label="Records"
            value={totalRecords.toLocaleString()}
          />

          <InfoBox
            label="Source"
            value={sourceOrg.name}
          />

          <InfoBox
            label="Target"
            value={targetOrg.name}
          />
        </div>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/5">
          <div className="flex gap-3">
            <AlertTriangle
              size={17}
              className="mt-0.5 shrink-0 text-amber-600"
            />

            <div>
              <p className="text-xs font-semibold text-amber-800 dark:text-amber-400">
                Review before execution
              </p>

              <p className="mt-1 text-xs leading-5 text-amber-700 dark:text-amber-500">
                ApexAI will migrate the selected objects in
                dependency order. Verify the target organization
                before continuing.
              </p>
            </div>
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-4 dark:border-zinc-800">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) =>
              setConfirmed(event.target.checked)
            }
            className="mt-0.5 h-4 w-4 accent-blue-600"
          />

          <span>
            <span className="block text-xs font-semibold text-slate-800 dark:text-zinc-200">
              I have reviewed this migration plan
            </span>

            <span className="mt-1 block text-[10px] text-slate-500 dark:text-zinc-500">
              I understand that execution will create or update
              records in the target organization.
            </span>
          </span>
        </label>

        <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-between dark:border-zinc-800">
          <button
            type="button"
            onClick={onBack}
            className="h-10 rounded-lg border border-slate-200 px-4 text-xs font-medium text-slate-600 dark:border-zinc-800 dark:text-zinc-300"
          >
            Back
          </button>

          <button
            type="button"
            disabled={!confirmed}
            onClick={onApprove}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ShieldCheck size={15} />
            Approve Migration
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </section>
  );
}

/* ========================================================= */
/* EXECUTE */
/* ========================================================= */

function ExecuteStep({
  isExecuting,
  progress,
  selectedData,
  onExecute,
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">

      <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
        <SectionHeader
          title="Execute Migration"
          description={
            isExecuting
              ? "ApexAI is migrating your Salesforce data."
              : "The migration has been approved and is ready to execute."
          }
        />
      </div>

      <div className="p-5">

        {!isExecuting && progress === 0 && (
          <div className="py-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
              <Play size={22} />
            </div>

            <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
              Ready to migrate
            </h3>

            <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-500 dark:text-zinc-500">
              ApexAI will process the selected objects according
              to the dependency-aware migration plan.
            </p>

            <button
              type="button"
              onClick={onExecute}
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white hover:bg-blue-700"
            >
              <Play size={15} />
              Start Migration
            </button>
          </div>
        )}

        {(isExecuting || progress > 0) && (
          <div className="space-y-5">

            <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-5 dark:border-blue-500/20 dark:bg-blue-500/5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                    Migration in progress
                  </p>

                  <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
                    Processing Salesforce records...
                  </p>
                </div>

                <span className="text-lg font-bold text-blue-600">
                  {progress}%
                </span>
              </div>

              <div className="mt-4 h-2 overflow-hidden rounded-full bg-blue-100 dark:bg-zinc-800">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-300"
                  style={{
                    width: `${progress}%`,
                  }}
                />
              </div>
            </div>

            <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 dark:divide-zinc-800 dark:border-zinc-800">
              {selectedData.map((object, index) => {
                const itemProgress = Math.max(
                  0,
                  Math.min(
                    100,
                    progress - index * 12
                  )
                );

                return (
                  <div
                    key={object.apiName}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    <Database
                      size={15}
                      className="text-blue-500"
                    />

                    <div className="flex-1">
                      <p className="text-xs font-medium text-slate-800 dark:text-zinc-200">
                        {object.name}
                      </p>

                      <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-100 dark:bg-zinc-800">
                        <div
                          className="h-full rounded-full bg-blue-500 transition-all duration-300"
                          style={{
                            width: `${itemProgress}%`,
                          }}
                        />
                      </div>
                    </div>

                    {itemProgress >= 100 ? (
                      <CheckCircle2
                        size={15}
                        className="text-emerald-500"
                      />
                    ) : (
                      <span className="text-[10px] text-slate-400">
                        {itemProgress}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

          </div>
        )}
      </div>
    </section>
  );
}

/* ========================================================= */
/* RESULTS */
/* ========================================================= */

function ResultsStep({
  selectedData,
  totalRecords,
  onStartOver,
}) {
  const successful = Math.max(
    0,
    totalRecords - 12
  );

  return (
    <div className="space-y-5">

      <section className="rounded-xl border border-emerald-200 bg-white dark:border-emerald-500/20 dark:bg-zinc-900">
        <div className="flex flex-col items-center px-5 py-10 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
            <CheckCircle2 size={27} />
          </div>

          <h2 className="mt-4 text-xl font-bold text-slate-900 dark:text-white">
            Migration Complete
          </h2>

          <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
            The migration has finished successfully.
          </p>
        </div>

        <div className="grid grid-cols-1 border-t border-emerald-100 sm:grid-cols-3 dark:border-zinc-800">
          <ResultMetric
            label="Records Processed"
            value={totalRecords.toLocaleString()}
          />

          <ResultMetric
            label="Successfully Migrated"
            value={successful.toLocaleString()}
          />

          <ResultMetric
            label="Failed"
            value="12"
            warning
          />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="border-b border-slate-200 p-5 dark:border-zinc-800">
          <SectionHeader
            title="Migration Summary"
            description="Objects processed during this migration."
          />
        </div>

        <div className="divide-y divide-slate-100 dark:divide-zinc-800">
          {selectedData.map((object) => (
            <div
              key={object.apiName}
              className="flex items-center gap-3 px-5 py-3.5"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                <Check size={15} />
              </div>

              <div className="flex-1">
                <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                  {object.name}
                </p>

                <p className="text-[10px] text-slate-400 dark:text-zinc-600">
                  {object.apiName}
                </p>
              </div>

              <span className="text-xs font-medium text-emerald-600">
                Completed
              </span>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end dark:border-zinc-800">
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-300"
          >
            View Errors
          </button>

          <button
            type="button"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-300"
          >
            <Upload size={14} />
            Download Report
          </button>

          <button
            type="button"
            onClick={onStartOver}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700"
          >
            <RotateCcw size={14} />
            New Migration
          </button>
        </div>
      </section>
    </div>
  );
}

/* ========================================================= */
/* SMALL COMPONENTS */
/* ========================================================= */

function SummaryMetric({
  label,
  value,
  icon: Icon,
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <Icon size={16} className="text-blue-500" />

      <p className="mt-3 text-xl font-bold text-slate-900 dark:text-white">
        {value}
      </p>

      <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
        {label}
      </p>
    </div>
  );
}

function InfoBox({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
        {label}
      </p>

      <p className="mt-1.5 text-sm font-semibold text-slate-800 dark:text-zinc-200">
        {value}
      </p>
    </div>
  );
}

function ResultMetric({
  label,
  value,
  warning = false,
}) {
  return (
    <div className="p-5 text-center">
      <p
        className={[
          "text-xl font-bold",
          warning
            ? "text-amber-600"
            : "text-slate-900 dark:text-white",
        ].join(" ")}
      >
        {value}
      </p>

      <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
        {label}
      </p>
    </div>
  );
}

export default Migration;