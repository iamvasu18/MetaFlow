import {
  Layers,
  Database,
  Zap,
  Code2,
  FileCheck2,
  GitBranch,
  ShieldCheck,
  Settings2,
} from "lucide-react";

import StatCard from "../../components/dashboard/StatCard";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/ui/EmptyState";

import dashboardData from "../../data/dashboardData";

function Metadata() {
  const data = dashboardData;

  const totalMetadata =
    data.metadata.customObjects +
    data.metadata.customFields +
    data.metadata.activeFlows +
    data.metadata.inactiveFlows +
    data.metadata.apexClasses +
    data.metadata.validationRules;

  return (
    <div className="space-y-4">

      {/* =================================================
          METADATA SUMMARY
      ================================================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Custom Objects"
          value={data.metadata.customObjects}
          subtitle="Custom objects in the org"
          icon={Layers}
          iconClass="text-blue-500"
        />

        <StatCard
          title="Custom Fields"
          value={data.metadata.customFields}
          subtitle="Custom fields across objects"
          icon={Database}
          iconClass="text-purple-500"
        />

        <StatCard
          title="Active Flows"
          value={data.metadata.activeFlows}
          subtitle="Currently active flows"
          icon={Zap}
          iconClass="text-emerald-500"
        />

        <StatCard
          title="Apex Classes"
          value={data.metadata.apexClasses}
          subtitle="Apex classes in the org"
          icon={Code2}
          iconClass="text-orange-500"
        />

      </div>

      {/* =================================================
          CONFIGURATION SUMMARY
      ================================================= */}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          title="Inactive Flows"
          value={data.metadata.inactiveFlows}
          subtitle="Inactive flow definitions"
          icon={GitBranch}
          iconClass="text-amber-500"
        />

        <StatCard
          title="Validation Rules"
          value={data.metadata.validationRules}
          subtitle="Validation rules configured"
          icon={FileCheck2}
          iconClass="text-red-500"
        />

        <StatCard
          title="Metadata Components"
          value={totalMetadata}
          subtitle="Tracked configuration components"
          icon={Settings2}
          iconClass="text-indigo-500"
        />

        <StatCard
          title="Metadata Health"
          value="Healthy"
          subtitle="No metadata issues detected"
          icon={ShieldCheck}
          iconClass="text-emerald-500"
        />

      </div>

      {/* =================================================
          METADATA CATEGORIES
      ================================================= */}

      <Card
        title="Metadata Categories"
        description="Salesforce configuration components detected in this organization"
        icon={Layers}
      >

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">

          <MetadataCategory
            icon={Layers}
            title="Custom Objects"
            value={data.metadata.customObjects}
            description="Custom Salesforce objects"
            status="Available"
          />

          <MetadataCategory
            icon={Database}
            title="Custom Fields"
            value={data.metadata.customFields}
            description="Custom fields and attributes"
            status="Available"
          />

          <MetadataCategory
            icon={Zap}
            title="Flows"
            value={
              data.metadata.activeFlows +
              data.metadata.inactiveFlows
            }
            description={`${data.metadata.activeFlows} active · ${data.metadata.inactiveFlows} inactive`}
            status="Available"
          />

          <MetadataCategory
            icon={Code2}
            title="Apex Classes"
            value={data.metadata.apexClasses}
            description="Apex classes and server-side logic"
            status="Available"
          />

          <MetadataCategory
            icon={FileCheck2}
            title="Validation Rules"
            value={data.metadata.validationRules}
            description="Validation rules configured"
            status="Available"
          />

          <MetadataCategory
            icon={ShieldCheck}
            title="Permissions"
            value="—"
            description="Permission data available after synchronization"
            status="Sync Required"
          />

        </div>

      </Card>

      {/* =================================================
          DETAILED METADATA
      ================================================= */}

      <Card
        title="Detailed Metadata"
        description="Detailed Salesforce metadata lists will be available after synchronization"
        icon={Settings2}
      >

        <EmptyState
          icon={Database}
          title="Detailed metadata not loaded"
          description="Re-sync the connected Salesforce organization to retrieve detailed objects, fields, flows, Apex classes, validation rules and other metadata."
        />

      </Card>

      {/* =================================================
          SYNCHRONIZATION
      ================================================= */}

      <Card
        title="Metadata Synchronization"
        description="Information about the latest metadata synchronization"
        icon={GitBranch}
      >

        <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800 dark:bg-zinc-900/50">

          <div className="flex items-center gap-3">

            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-500 dark:bg-blue-500/10">
              <GitBranch size={15} />
            </div>

            <div>

              <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                Metadata synchronization
              </p>

              <p className="mt-0.5 text-[9px] text-slate-500 dark:text-zinc-500">
                Last synchronized: {data.sync.lastSynced}
              </p>

            </div>

          </div>

          <Badge variant="success" dot>
            Synchronized
          </Badge>

        </div>

      </Card>

    </div>
  );
}

/* =====================================================
   METADATA CATEGORY
===================================================== */

function MetadataCategory({
  icon: Icon,
  title,
  value,
  description,
  status,
}) {
  const isSyncRequired = status === "Sync Required";

  return (
    <div className="group flex items-start gap-3 rounded-lg border border-slate-200 p-3 transition hover:border-blue-200 hover:bg-blue-50/30 dark:border-zinc-800 dark:hover:border-blue-500/20 dark:hover:bg-blue-500/5">

      {/* Icon */}

      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-blue-500 dark:bg-zinc-900">
        <Icon size={15} />
      </div>

      {/* Content */}

      <div className="min-w-0 flex-1">

        <div className="flex items-center justify-between gap-2">

          <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
            {title}
          </p>

          <p className="text-sm font-semibold text-slate-900 dark:text-white">
            {value}
          </p>

        </div>

        <p className="mt-0.5 text-[9px] leading-4 text-slate-500 dark:text-zinc-500">
          {description}
        </p>

        <div className="mt-2">
          <Badge
            variant={isSyncRequired ? "warning" : "success"}
            dot
          >
            {status}
          </Badge>
        </div>

      </div>

    </div>
  );
}

export default Metadata;