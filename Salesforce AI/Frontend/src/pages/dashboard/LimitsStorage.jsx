import {
  Activity,
  Database,
  HardDrive,
  Clock3,
  Zap,
  Mail,
  Radio,
  BarChart3,
  Globe,
} from "lucide-react";

import StatCard from "../../components/dashboard/StatCard";
import Card from "../../components/ui/Card";
import ProgressBar from "../../components/ui/ProgressBar";
import Badge from "../../components/ui/Badge";

import dashboardData from "../../data/dashboardData";

function LimitsStorage() {
  const data = dashboardData;

  /* =====================================================
     CALCULATIONS
  ===================================================== */

  const dataStoragePercentage =
    data.storage.dataLimit > 0
      ? (data.storage.dataUsed / data.storage.dataLimit) * 100
      : 0;

  const fileStoragePercentage =
    data.storage.fileLimit > 0
      ? (data.storage.fileUsed / data.storage.fileLimit) * 100
      : 0;

  const scheduledJobsPercentage =
    data.scheduledJobs?.limit > 0
      ? (data.scheduledJobs.used / data.scheduledJobs.limit) * 100
      : 0;

  /* =====================================================
     PAGE
  ===================================================== */

  return (
    <div className="space-y-4">

      {/* =================================================
          SUMMARY CARDS
      ================================================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        {/* Data Storage */}

        <StatCard
          title="Data Storage"
          value={`${data.storage.dataUsed} GB`}
          subtitle={`${data.storage.dataLimit} GB total`}
          icon={Database}
          iconClass="text-blue-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={dataStoragePercentage}
              variant={
                dataStoragePercentage >= 90
                  ? "danger"
                  : dataStoragePercentage >= 75
                    ? "warning"
                    : "success"
              }
            />
          </div>
        </StatCard>

        {/* File Storage */}

        <StatCard
          title="File Storage"
          value={`${data.storage.fileUsed} GB`}
          subtitle={`${data.storage.fileLimit} GB total`}
          icon={HardDrive}
          iconClass="text-purple-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={fileStoragePercentage}
              variant={
                fileStoragePercentage >= 90
                  ? "danger"
                  : fileStoragePercentage >= 75
                    ? "warning"
                    : "success"
              }
            />
          </div>
        </StatCard>

        {/* API Requests */}

        <StatCard
          title="API Requests"
          value={`${data.api.percentage}%`}
          subtitle={`${data.api.used.toLocaleString()} / ${data.api.limit.toLocaleString()}`}
          icon={Activity}
          iconClass="text-orange-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={data.api.percentage}
              variant={
                data.api.percentage >= 90
                  ? "danger"
                  : data.api.percentage >= 75
                    ? "warning"
                    : "success"
              }
            />
          </div>
        </StatCard>

        {/* Scheduled Jobs */}

        <StatCard
          title="Scheduled Jobs"
          value={data.scheduledJobs?.used ?? 0}
          subtitle={
            data.scheduledJobs
              ? `${data.scheduledJobs.limit} concurrent jobs available`
              : "No job data available"
          }
          icon={Clock3}
          iconClass="text-emerald-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={scheduledJobsPercentage}
              variant={
                scheduledJobsPercentage >= 90
                  ? "danger"
                  : scheduledJobsPercentage >= 75
                    ? "warning"
                    : "success"
              }
            />
          </div>
        </StatCard>

      </div>

      {/* =================================================
          STORAGE
      ================================================= */}

      <Card
        title="Storage"
        description="Salesforce data and file storage utilization"
        icon={Database}
      >

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">

          <StorageItem
            title="Data Storage"
            used={data.storage.dataUsed}
            limit={data.storage.dataLimit}
            unit="GB"
            icon={Database}
          />

          <StorageItem
            title="File Storage"
            used={data.storage.fileUsed}
            limit={data.storage.fileLimit}
            unit="GB"
            icon={HardDrive}
          />

        </div>

      </Card>

      {/* =================================================
          API LIMITS
      ================================================= */}

      <Card
        title="API Limits"
        description="Salesforce API consumption and daily limits"
        icon={Activity}
      >

        <div className="grid grid-cols-1 gap-x-6 gap-y-4 lg:grid-cols-2">

          <LimitItem
            label="Daily API Requests"
            used={data.limits.dailyApiRequests.used}
            limit={data.limits.dailyApiRequests.limit}
            icon={Activity}
          />

          <LimitItem
            label="Daily Async Apex Executions"
            used={data.limits.dailyAsyncApex.used}
            limit={data.limits.dailyAsyncApex.limit}
            icon={Zap}
          />

          <LimitItem
            label="Daily Workflow Emails"
            used={data.limits.workflowEmails.used}
            limit={data.limits.workflowEmails.limit}
            icon={Mail}
          />

          <LimitItem
            label="Streaming API Clients"
            used={data.limits.streamingApiClients.used}
            limit={data.limits.streamingApiClients.limit}
            icon={Radio}
          />

        </div>

      </Card>

      {/* =================================================
          GOVERNOR LIMITS
      ================================================= */}

      <Card
        title="Governor Limits"
        description="Current Salesforce platform resource consumption"
        icon={Zap}
      >

        <div className="grid grid-cols-1 gap-x-6 gap-y-4 lg:grid-cols-2">

          <LimitItem
            label="Single Email"
            used={data.limits.singleEmail.used}
            limit={data.limits.singleEmail.limit}
            icon={Mail}
          />

          <LimitItem
            label="Mass Email"
            used={data.limits.massEmail.used}
            limit={data.limits.massEmail.limit}
            icon={Mail}
          />

          <LimitItem
            label="Hourly Dashboard Results"
            used={data.limits.dashboardResults.used}
            limit={data.limits.dashboardResults.limit}
            icon={BarChart3}
          />

          <LimitItem
            label="Daily Callouts"
            used={data.limits.callouts.used}
            limit={data.limits.callouts.limit}
            icon={Globe}
          />

        </div>

      </Card>

      {/* =================================================
          LIMIT HEALTH
      ================================================= */}

      <Card
        title="Limit Health"
        description="Overall status of Salesforce resource utilization"
        icon={Activity}
      >

        <div className="flex flex-col gap-3 rounded-lg border border-emerald-100 bg-emerald-50/50 p-3 sm:flex-row sm:items-center sm:justify-between dark:border-emerald-500/10 dark:bg-emerald-500/5">

          <div className="flex items-center gap-3">

            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
              <Activity size={15} />
            </div>

            <div>

              <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                Limits are within healthy range
              </p>

              <p className="mt-0.5 text-[9px] text-slate-500 dark:text-zinc-500">
                No Salesforce resource limit currently requires attention.
              </p>

            </div>

          </div>

          <Badge variant="success" dot>
            Healthy
          </Badge>

        </div>

      </Card>

    </div>
  );
}

/* =====================================================
   STORAGE ITEM
===================================================== */

function StorageItem({
  title,
  used,
  limit,
  unit,
  icon: Icon,
}) {
  const percentage =
    limit > 0
      ? (used / limit) * 100
      : 0;

  const variant =
    percentage >= 90
      ? "danger"
      : percentage >= 75
        ? "warning"
        : "success";

  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">

      <div className="flex items-center justify-between">

        <div className="flex items-center gap-2">

          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 text-blue-500 dark:bg-zinc-900">
            <Icon size={14} />
          </div>

          <div>
            <p className="text-xs font-medium text-slate-700 dark:text-zinc-300">
              {title}
            </p>

            <p className="text-[9px] text-slate-400 dark:text-zinc-600">
              Storage utilization
            </p>
          </div>

        </div>

        <p className="text-xs font-semibold text-slate-900 dark:text-white">
          {percentage.toFixed(0)}%
        </p>

      </div>

      <div className="mt-3">

        <ProgressBar
          value={percentage}
          variant={variant}
        />

      </div>

      <div className="mt-1.5 flex justify-between">

        <span className="text-[9px] text-slate-400 dark:text-zinc-600">
          {used} {unit} used
        </span>

        <span className="text-[9px] text-slate-400 dark:text-zinc-600">
          {limit} {unit}
        </span>

      </div>

    </div>
  );
}

/* =====================================================
   LIMIT ITEM
===================================================== */

function LimitItem({
  label,
  used,
  limit,
  icon: Icon,
}) {
  const percentage =
    limit > 0
      ? (used / limit) * 100
      : 0;

  let variant = "success";

  if (percentage >= 90) {
    variant = "danger";
  } else if (percentage >= 75) {
    variant = "warning";
  }

  const remaining = Math.max(
    0,
    100 - percentage
  );

  return (
    <div>

      {/* Header */}

      <div className="mb-1.5 flex items-center justify-between gap-3">

        <div className="flex min-w-0 items-center gap-2">

          <Icon
            size={13}
            className="shrink-0 text-slate-400 dark:text-zinc-600"
          />

          <span className="truncate text-[10px] font-medium text-slate-600 dark:text-zinc-400">
            {label}
          </span>

        </div>

        <span className="shrink-0 text-[9px] font-semibold text-slate-600 dark:text-zinc-400">
          {used.toLocaleString()} /{" "}
          {limit.toLocaleString()}
        </span>

      </div>

      {/* Progress */}

      <ProgressBar
        value={percentage}
        variant={variant}
      />

      {/* Footer */}

      <div className="mt-1 flex justify-between">

        <span className="text-[8px] text-slate-400 dark:text-zinc-600">
          {percentage.toFixed(1)}% used
        </span>

        <span
          className={`text-[8px] ${
            variant === "danger"
              ? "text-red-500"
              : variant === "warning"
                ? "text-amber-500"
                : "text-emerald-500"
          }`}
        >
          {remaining.toFixed(1)}% remaining
        </span>

      </div>

    </div>
  );
}

export default LimitsStorage;