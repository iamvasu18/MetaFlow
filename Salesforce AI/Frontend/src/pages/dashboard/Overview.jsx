import {
  Activity,
  Database,
  HardDrive,
  Users,
  ShieldCheck,
  UserX,
  UserRoundX,
  Layers,
  Zap,
  Code2,
  FileCheck2,
  Cloud,
  Upload,
  GitBranch,
  AlertTriangle,
} from "lucide-react";

import { useOrg } from "../../context/OrgContext";

import StatCard from "../../components/dashboard/StatCard";
import Card from "../../components/ui/Card";
import ProgressBar from "../../components/ui/ProgressBar";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/ui/EmptyState";

import dashboardData from "../../data/dashboardData";

function Overview() {
  const { activeOrg } = useOrg();

  const data = dashboardData;

  const dataStoragePercentage =
    (data.storage.dataUsed / data.storage.dataLimit) * 100;

  const fileStoragePercentage =
    (data.storage.fileUsed / data.storage.fileLimit) * 100;

  return (
    <div className="space-y-4">

      {/* Organization */}

      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-slate-950 dark:text-white">
              {activeOrg?.name || data.organization.name}
            </h2>

            <Badge variant="success" dot>
              {data.organization.status}
            </Badge>
          </div>

          <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
            {data.organization.environment} · Salesforce{" "}
            {data.organization.apiVersion}
          </p>
        </div>
      </div>

      {/* ================= KPI ROW 1 ================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Health Score"
          value={data.health.score}
          subtitle="Overall organization health"
          icon={ShieldCheck}
          iconClass="text-blue-500"
        />

        <StatCard
          title="API Usage"
          value={`${data.api.percentage}%`}
          subtitle={`${data.api.used.toLocaleString()} / ${data.api.limit.toLocaleString()} requests`}
          icon={Activity}
          iconClass="text-orange-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={data.api.percentage}
              variant="success"
            />
          </div>
        </StatCard>

        <StatCard
          title="Data Storage"
          value={`${dataStoragePercentage.toFixed(0)}%`}
          subtitle={`${data.storage.dataUsed} GB / ${data.storage.dataLimit} GB`}
          icon={Database}
          iconClass="text-purple-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={dataStoragePercentage}
              variant="success"
            />
          </div>
        </StatCard>

        <StatCard
          title="File Storage"
          value={`${fileStoragePercentage.toFixed(0)}%`}
          subtitle={`${data.storage.fileUsed} GB / ${data.storage.fileLimit} GB`}
          icon={HardDrive}
          iconClass="text-emerald-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={fileStoragePercentage}
              variant="success"
            />
          </div>
        </StatCard>

      </div>

      {/* ================= KPI ROW 2 ================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Licenses"
          value={`${data.licenses.used}/${data.licenses.total}`}
          subtitle="Licenses currently assigned"
          icon={Users}
          iconClass="text-indigo-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={
                (data.licenses.used /
                  data.licenses.total) *
                100
              }
            />
          </div>
        </StatCard>

        <StatCard
          title="User Adoption"
          value={`${data.users.adoptionRate}%`}
          subtitle={`${data.users.active} active users`}
          icon={Users}
          iconClass="text-blue-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={data.users.adoptionRate}
              variant="success"
            />
          </div>
        </StatCard>

        <StatCard
          title="Never Logged In"
          value={data.users.total - data.users.active}
          subtitle="Users without recent activity"
          icon={UserX}
          iconClass="text-amber-500"
        />

        <StatCard
          title="Frozen Users"
          value={0}
          subtitle="Currently frozen accounts"
          icon={UserRoundX}
          iconClass="text-red-500"
        />

      </div>

      {/* ================= CHARTS ================= */}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.65fr_1fr]">

        <Card
          title="API Usage Trend"
          description="Daily API calls over the last 7 days"
          icon={Activity}
          action={
            <select className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-600 outline-none dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
              <option>7 Days</option>
              <option>30 Days</option>
            </select>
          }
        >
          <ApiTrendChart data={data.apiTrend} />
        </Card>

        <Card
          title="Storage Breakdown"
          description="Current storage allocation"
          icon={Database}
        >
          <StorageBreakdown data={data.storage} />
        </Card>

      </div>

      {/* ================= ACTIVITY ================= */}

      <Card
        title="Recent Activity"
        description="Latest events from your Salesforce organization"
        icon={Activity}
      >
        <div className="divide-y divide-slate-100 dark:divide-zinc-800">

          {data.recentActivity.map((item) => (
            <ActivityRow
              key={item.id}
              item={item}
            />
          ))}

        </div>
      </Card>

      {/* ================= METADATA ================= */}

      <Card
        title="Metadata Overview"
        description="Salesforce configuration at a glance"
        icon={Layers}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">

          <MetadataItem
            icon={Layers}
            label="Custom Objects"
            value={data.metadata.customObjects}
          />

          <MetadataItem
            icon={Database}
            label="Custom Fields"
            value={data.metadata.customFields}
          />

          <MetadataItem
            icon={Zap}
            label="Active Flows"
            value={data.metadata.activeFlows}
          />

          <MetadataItem
            icon={Zap}
            label="Inactive Flows"
            value={data.metadata.inactiveFlows}
          />

          <MetadataItem
            icon={Code2}
            label="Apex Classes"
            value={data.metadata.apexClasses}
          />

          <MetadataItem
            icon={FileCheck2}
            label="Validation Rules"
            value={data.metadata.validationRules}
          />

        </div>
      </Card>

      {/* ================= HEALTH ================= */}

      <Card
        title="Health Score Breakdown"
        description="Factors contributing to your organization health"
        icon={ShieldCheck}
      >
        <div className="grid gap-4 md:grid-cols-2">

          <ScoreItem
            label="API Headroom"
            value={data.scoreBreakdown.apiHeadroom}
          />

          <ScoreItem
            label="License Availability"
            value={data.scoreBreakdown.licenseAvailability}
          />

          <ScoreItem
            label="Storage Headroom"
            value={data.scoreBreakdown.storageHeadroom}
          />

          <ScoreItem
            label="User Adoption"
            value={data.scoreBreakdown.userAdoption}
          />

        </div>
      </Card>

      {/* ================= INDUSTRY ================= */}

      <Card
        title="Industry Clouds"
        description="Salesforce industry solutions detected"
        icon={Cloud}
      >
        {data.industryClouds.length === 0 ? (
          <EmptyState
            icon={Cloud}
            title="No industry clouds detected"
            description="Industry Cloud information will appear here when detected during synchronization."
          />
        ) : (
          <div>
            Industry cloud data
          </div>
        )}
      </Card>

    </div>
  );
}

/* ========================= */

function ApiTrendChart() {
  const points = [48, 58, 63, 51, 74, 68, 82];

  return (
    <div className="pt-3">

      <div className="flex h-36 items-end gap-2">

        {points.map((point, index) => (
          <div
            key={index}
            className="flex flex-1 flex-col items-center justify-end gap-1"
          >
            <div
              className="w-full max-w-10 rounded-t-md bg-blue-500/80 transition hover:bg-blue-600"
              style={{
                height: `${point}%`,
              }}
            />

            <span className="text-[9px] text-slate-400 dark:text-zinc-600">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][index]}
            </span>
          </div>
        ))}

      </div>

    </div>
  );
}

/* ========================= */

function StorageBreakdown({ data }) {
  const total =
    data.dataUsed +
    data.fileUsed +
    47.9;

  const dataPercentage =
    (data.dataUsed / total) * 100;

  const filePercentage =
    (data.fileUsed / total) * 100;

  return (
    <div className="flex items-center gap-5">

      <div className="relative h-32 w-32 shrink-0 rounded-full bg-slate-100 dark:bg-zinc-800">

        <div
          className="absolute inset-3 rounded-full bg-white dark:bg-zinc-950"
        />

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-semibold">
            {total.toFixed(1)} GB
          </span>

          <span className="text-[9px] text-slate-400">
            Total
          </span>
        </div>

      </div>

      <div className="space-y-3 text-xs">

        <Legend
          color="bg-purple-500"
          label="Data Storage"
          value={`${data.dataUsed} GB (${dataPercentage.toFixed(0)}%)`}
        />

        <Legend
          color="bg-emerald-500"
          label="File Storage"
          value={`${data.fileUsed} GB (${filePercentage.toFixed(0)}%)`}
        />

        <Legend
          color="bg-slate-300"
          label="Other Storage"
          value="47.9 GB"
        />

      </div>

    </div>
  );
}

/* ========================= */

function Legend({ color, label, value }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${color}`} />

      <div>
        <p className="font-medium text-slate-600 dark:text-zinc-300">
          {label}
        </p>

        <p className="text-[10px] text-slate-400">
          {value}
        </p>
      </div>
    </div>
  );
}

/* ========================= */

function ActivityRow({ item }) {
  const icons = {
    deployment: GitBranch,
    migration: GitBranch,
    import: Upload,
    warning: AlertTriangle,
    user: Users,
  };

  const Icon = icons[item.type] || Activity;

  return (
    <div className="flex items-center gap-3 py-2.5">

      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-50 text-blue-500 dark:bg-zinc-900">
        <Icon size={13} />
      </div>

      <div className="min-w-0 flex-1">

        <p className="truncate text-[11px] font-medium text-slate-700 dark:text-zinc-300">
          {item.title}
        </p>

        <p className="text-[9px] text-slate-400">
          {item.user}
        </p>

      </div>

      <span className="text-[9px] text-slate-400">
        {item.time}
      </span>

    </div>
  );
}

/* ========================= */

function MetadataItem({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-zinc-900/60">

      <Icon
        size={14}
        className="text-blue-500"
      />

      <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">
        {value}
      </p>

      <p className="text-[9px] text-slate-400">
        {label}
      </p>

    </div>
  );
}

/* ========================= */

function ScoreItem({ label, value }) {
  const variant =
    value < 40
      ? "danger"
      : value < 70
        ? "warning"
        : "success";

  return (
    <div>

      <div className="mb-1.5 flex justify-between">
        <span className="text-[10px] text-slate-500">
          {label}
        </span>

        <span className="text-[10px] font-semibold">
          {value}
        </span>
      </div>

      <ProgressBar
        value={value}
        variant={variant}
      />

    </div>
  );
}

export default Overview;