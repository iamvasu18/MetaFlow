import {
  Users,
  ShieldCheck,
  UserCheck,
  UserX,
  UserRoundX,
  KeyRound,
  LockKeyhole,
  Activity,
} from "lucide-react";

import StatCard from "../../components/dashboard/StatCard";
import Card from "../../components/ui/Card";
import ProgressBar from "../../components/ui/ProgressBar";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/ui/EmptyState";

import dashboardData from "../../data/dashboardData";

function LicensesUsers() {
  const data = dashboardData;

  const licensePercentage =
    data.licenses.total > 0
      ? (data.licenses.used / data.licenses.total) * 100
      : 0;

  const inactiveUsers =
    data.users.total - data.users.active;

  const adoptionRate = data.users.adoptionRate;

  return (
    <div className="space-y-4">

      {/* ================================================= */}
      {/* LICENSE SUMMARY */}
      {/* ================================================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Total Licenses"
          value={data.licenses.total}
          subtitle="Available Salesforce licenses"
          icon={KeyRound}
          iconClass="text-blue-500"
        />

        <StatCard
          title="Licenses Used"
          value={data.licenses.used}
          subtitle={`${licensePercentage.toFixed(0)}% of total licenses`}
          icon={UserCheck}
          iconClass="text-purple-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={licensePercentage}
              variant={
                licensePercentage >= 90
                  ? "warning"
                  : "success"
              }
            />
          </div>
        </StatCard>

        <StatCard
          title="Available Licenses"
          value={
            data.licenses.total -
            data.licenses.used
          }
          subtitle="Licenses available for assignment"
          icon={ShieldCheck}
          iconClass="text-emerald-500"
        />

        <StatCard
          title="Total Users"
          value={data.users.total}
          subtitle="Users in this organization"
          icon={Users}
          iconClass="text-blue-500"
        />

      </div>

      {/* ================================================= */}
      {/* USER ADOPTION */}
      {/* ================================================= */}

      <Card
        title="User Adoption"
        description="User activity and adoption across the Salesforce organization"
        icon={Users}
      >

        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">

          {/* Adoption */}
          <div>

            <div className="flex items-end justify-between">

              <div>
                <p className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
                  {adoptionRate}%
                </p>

                <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
                  Overall user adoption
                </p>
              </div>

              <Badge
                variant={
                  adoptionRate >= 80
                    ? "success"
                    : "warning"
                }
                dot
              >
                {adoptionRate >= 80
                  ? "Healthy"
                  : "Needs Attention"}
              </Badge>

            </div>

            <div className="mt-4">
              <ProgressBar
                value={adoptionRate}
                variant={
                  adoptionRate >= 80
                    ? "success"
                    : "warning"
                }
              />
            </div>

            <div className="mt-1.5 flex justify-between text-[9px] text-slate-400 dark:text-zinc-600">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>

          </div>

          {/* Adoption Metrics */}

          <div className="grid grid-cols-2 gap-2">

            <MiniMetric
              label="Active"
              value={data.users.active}
              icon={UserCheck}
              iconClass="text-emerald-500"
            />

            <MiniMetric
              label="Inactive"
              value={inactiveUsers}
              icon={UserX}
              iconClass="text-amber-500"
            />

            <MiniMetric
              label="Never Logged In"
              value={inactiveUsers}
              icon={UserRoundX}
              iconClass="text-red-500"
            />

            <MiniMetric
              label="Frozen"
              value={0}
              icon={LockKeyhole}
              iconClass="text-red-500"
            />

          </div>

        </div>

      </Card>

      {/* ================================================= */}
      {/* USER STATUS */}
      {/* ================================================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Active Users"
          value={data.users.active}
          subtitle="Users with recent activity"
          icon={UserCheck}
          iconClass="text-emerald-500"
        />

        <StatCard
          title="Never Logged In"
          value={inactiveUsers}
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

        <StatCard
          title="Adoption Rate"
          value={`${adoptionRate}%`}
          subtitle="30-day user activity"
          icon={Users}
          iconClass="text-blue-500"
        >
          <div className="mt-3">
            <ProgressBar
              value={adoptionRate}
              variant="success"
            />
          </div>
        </StatCard>

      </div>

      {/* ================================================= */}
      {/* PERMISSION SPRAWL + LOGIN SECURITY */}
      {/* ================================================= */}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">

        <Card
          title="Permission Sprawl"
          description="Permission and access information"
          icon={ShieldCheck}
          action={
            <span className="text-[10px] text-slate-400">
              Active users
            </span>
          }
        >

          <EmptyState
            icon={LockKeyhole}
            title="Permission data not available"
            description="Re-sync the Salesforce organization to fetch profiles, permission sets, roles and access information."
          />

        </Card>

        <Card
          title="Login Security"
          description="Login activity and security information"
          icon={Activity}
          action={
            <span className="text-[10px] text-slate-400">
              Last 30 days
            </span>
          }
        >

          <EmptyState
            icon={LockKeyhole}
            title="Login history not available"
            description="Re-sync the Salesforce organization to fetch login history and security information."
          />

        </Card>

      </div>

      {/* ================================================= */}
      {/* LICENSE DETAILS */}
      {/* ================================================= */}

      <Card
        title="License Details"
        description="Salesforce license allocation"
        icon={KeyRound}
      >

        <div className="overflow-x-auto">

          <table className="w-full min-w-[600px] text-left">

            <thead>

              <tr className="border-b border-slate-200 dark:border-zinc-800">

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  License
                </th>

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  Total
                </th>

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  Used
                </th>

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  Available
                </th>

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  Usage
                </th>

                <th className="px-3 py-2.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-600">
                  Status
                </th>

              </tr>

            </thead>

            <tbody>

              <tr className="border-b border-slate-100 dark:border-zinc-900">

                <td className="px-3 py-3">

                  <p className="text-xs font-medium text-slate-700 dark:text-zinc-300">
                    Salesforce Platform
                  </p>

                  <p className="mt-0.5 text-[9px] text-slate-400">
                    Standard user license
                  </p>

                </td>

                <td className="px-3 py-3 text-xs text-slate-500 dark:text-zinc-500">
                  {data.licenses.total}
                </td>

                <td className="px-3 py-3 text-xs text-slate-500 dark:text-zinc-500">
                  {data.licenses.used}
                </td>

                <td className="px-3 py-3 text-xs text-slate-500 dark:text-zinc-500">
                  {data.licenses.total -
                    data.licenses.used}
                </td>

                <td className="px-3 py-3">

                  <div className="w-24">

                    <ProgressBar
                      value={licensePercentage}
                      variant={
                        licensePercentage >= 90
                          ? "warning"
                          : "success"
                      }
                    />

                    <p className="mt-1 text-[9px] text-slate-400">
                      {licensePercentage.toFixed(0)}% used
                    </p>

                  </div>

                </td>

                <td className="px-3 py-3">

                  <Badge
                    variant={
                      licensePercentage >= 90
                        ? "warning"
                        : "success"
                    }
                    dot
                  >
                    {licensePercentage >= 90
                      ? "High Usage"
                      : "Healthy"}
                  </Badge>

                </td>

              </tr>

            </tbody>

          </table>

        </div>

      </Card>

    </div>
  );
}

/* ================================================= */
/* MINI METRIC */
/* ================================================= */

function MiniMetric({
  label,
  value,
  icon: Icon,
  iconClass = "text-blue-500",
}) {
  return (
    <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-zinc-900/60">

      <div className="flex items-center justify-between">

        <Icon
          size={14}
          className={iconClass}
        />

      </div>

      <p className="mt-1.5 text-base font-semibold text-slate-900 dark:text-white">
        {value}
      </p>

      <p className="mt-0.5 text-[9px] text-slate-500 dark:text-zinc-500">
        {label}
      </p>

    </div>
  );
}

export default LicensesUsers;