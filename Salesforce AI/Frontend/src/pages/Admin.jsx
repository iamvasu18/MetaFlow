import { useState } from "react";

import {
  Building2,
  Users,
  ShieldCheck,
  GitBranch,
  Plus,
  Cloud,
  MoreHorizontal,
  Trash2,
  Settings2,
  UserPlus,
  LockKeyhole,
  RefreshCw,
  ExternalLink,
  Database,
  Globe2,
  ChevronDown,
  X,
  Save,
  AlertCircle,
} from "lucide-react";

import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

/* =========================================================
   ADMIN TABS
========================================================= */

const tabs = [
  {
    id: "organizations",
    label: "Organizations",
    icon: Building2,
  },
  {
    id: "members",
    label: "Members",
    icon: Users,
  },
  {
    id: "governance",
    label: "Governance",
    icon: ShieldCheck,
  },
  {
    id: "git",
    label: "Git",
    icon: GitBranch,
  },
];

/* =========================================================
   SAMPLE DATA
   Replace these with API/backend data later.
========================================================= */

const initialOrganizations = [
  {
    id: 1,
    name: "Acme Corp Production",
    environment: "Production",
    apiVersion: "v60.0",
    status: "Connected",
    username: "admin@acmecorp.com",
    isDefault: true,
  },
];

const initialMembers = [
  {
    id: 1,
    name: "Priya Nair",
    email: "priya.nair@acmecorp.com",
    role: "Admin",
    status: "Active",
    initials: "PN",
    you: true,
  },
  {
    id: 2,
    name: "Arjun Mehta",
    email: "arjun.mehta@acmecorp.com",
    role: "Builder",
    status: "Active",
    initials: "AM",
    you: false,
  },
  {
    id: 3,
    name: "Riya Sharma",
    email: "riya.sharma@acmecorp.com",
    role: "Approver",
    status: "Active",
    initials: "RS",
    you: false,
  },
];

const roles = [
  {
    name: "Admin",
    description:
      "Full access — manage members, settings, connections, plans, and approvals.",
  },
  {
    name: "Approver",
    description:
      "Approve or reject promotion requests. Can also build and submit requests.",
  },
  {
    name: "Builder",
    description:
      "Create and edit implementation plans, run agent work, and request promotions.",
  },
  {
    name: "Releaser",
    description:
      "Execute approved promotions to production. Cannot approve their own requests.",
  },
  {
    name: "Requester",
    description:
      "Submit requests and review outputs. Read-only on most administration surfaces.",
  },
];

/* =========================================================
   MAIN ADMIN PAGE
========================================================= */

function Admin() {
  const [activeTab, setActiveTab] = useState("organizations");

  const [organizations, setOrganizations] = useState(
    initialOrganizations
  );

  const [members, setMembers] = useState(initialMembers);

  const [showConnectModal, setShowConnectModal] = useState(false);

  return (
    <div className="min-h-[calc(100vh-68px)] bg-slate-50 px-4 py-6 dark:bg-zinc-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1180px]">

        {/* =================================================
            PAGE HEADER
        ================================================= */}

        <div className="mb-7">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">

            <div>
              <div className="flex items-center gap-2">

                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  <Settings2 size={19} strokeWidth={1.8} />
                </div>

                <div>
                  <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                    Workspace Admin
                  </h1>

                  <p className="mt-0.5 text-xs text-slate-500 dark:text-zinc-500">
                    Manage environments, members, governance and integrations.
                  </p>
                </div>

              </div>
            </div>

            {organizations.length === 0 && (
              <button
                type="button"
                onClick={() => setShowConnectModal(true)}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700"
              >
                <Plus size={15} />
                Connect Salesforce Org
              </button>
            )}

          </div>
        </div>

        {/* =================================================
            TABS
        ================================================= */}

        <div className="mb-6 border-b border-slate-200 dark:border-zinc-800">
          <div className="flex gap-1 overflow-x-auto">

            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "relative flex shrink-0 items-center gap-2 px-4 py-3 text-xs font-medium transition",
                    isActive
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-slate-500 hover:text-slate-900 dark:text-zinc-400 dark:hover:text-white",
                  ].join(" ")}
                >
                  <Icon size={15} strokeWidth={1.8} />

                  {tab.label}

                  {tab.id === "organizations" &&
                    organizations.length > 0 && (
                      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-500 dark:bg-zinc-800 dark:text-zinc-400">
                        {organizations.length}
                      </span>
                    )}

                  {tab.id === "members" && (
                    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {members.length}
                    </span>
                  )}

                  {isActive && (
                    <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-blue-600 dark:bg-blue-400" />
                  )}
                </button>
              );
            })}

          </div>
        </div>

        {/* =================================================
            TAB CONTENT
        ================================================= */}

        {activeTab === "organizations" && (
          <OrganizationsTab
            organizations={organizations}
            onConnect={() => setShowConnectModal(true)}
            onSetDefault={(id) => {
              setOrganizations((current) =>
                current.map((org) => ({
                  ...org,
                  isDefault: org.id === id,
                }))
              );
            }}
            onDisconnect={(id) => {
              setOrganizations((current) =>
                current.filter((org) => org.id !== id)
              );
            }}
          />
        )}

        {activeTab === "members" && (
          <MembersTab
            members={members}
            setMembers={setMembers}
          />
        )}

        {activeTab === "governance" && <GovernanceTab />}

        {activeTab === "git" && <GitTab />}

      </div>

      {/* =================================================
          CONNECT MODAL
      ================================================= */}

      {showConnectModal && (
        <ConnectOrgModal
          onClose={() => setShowConnectModal(false)}
          onConnect={(organization) => {
            setOrganizations((current) => [
              ...current,
              {
                ...organization,
                id: Date.now(),
                status: "Connected",
              },
            ]);

            setShowConnectModal(false);
          }}
        />
      )}

    </div>
  );
}

/* =========================================================
   ORGANIZATIONS
========================================================= */

function OrganizationsTab({
  organizations,
  onConnect,
  onSetDefault,
  onDisconnect,
}) {
  return (
    <div className="space-y-5">

      {/* Header */}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

        <div>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            Salesforce Organizations
          </h2>

          <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
            Connect and manage the Salesforce environments used by ApexAI.
          </p>
        </div>

        <button
          type="button"
          onClick={onConnect}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white transition hover:bg-blue-700"
        >
          <Plus size={15} />
          Connect Org
        </button>

      </div>

      {/* Empty State */}

      {organizations.length === 0 && (
        <Card>
          <div className="flex min-h-[350px] flex-col items-center justify-center px-6 text-center">

            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-500 dark:bg-blue-500/10 dark:text-blue-400">
              <Database size={25} strokeWidth={1.7} />
            </div>

            <h3 className="mt-5 text-base font-semibold text-slate-900 dark:text-white">
              No Salesforce orgs connected
            </h3>

            <p className="mt-2 max-w-md text-xs leading-5 text-slate-500 dark:text-zinc-500">
              Connect your first Salesforce organization to enable
              intelligence, AI workspace, imports and migrations.
            </p>

            <button
              type="button"
              onClick={onConnect}
              className="mt-6 inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700"
            >
              <Plus size={15} />
              Connect Salesforce Org
            </button>

          </div>
        </Card>
      )}

      {/* Organization Cards */}

      {organizations.length > 0 && (
        <div className="space-y-3">

          {organizations.map((org) => (
            <div
              key={org.id}
              className="rounded-xl border border-slate-200 bg-white transition hover:border-blue-200 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-blue-500/30"
            >

              <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">

                <div className="flex min-w-0 items-start gap-4">

                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                    <Cloud size={20} strokeWidth={1.8} />
                  </div>

                  <div className="min-w-0">

                    <div className="flex flex-wrap items-center gap-2">

                      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                        {org.name}
                      </h3>

                      <Badge variant="success" dot>
                        Connected
                      </Badge>

                      {org.isDefault && (
                        <Badge variant="info">
                          Default
                        </Badge>
                      )}

                    </div>

                    <p className="mt-1 text-xs text-slate-500 dark:text-zinc-500">
                      {org.environment} · Salesforce API {org.apiVersion}
                    </p>

                    <p className="mt-1 text-[10px] text-slate-400 dark:text-zinc-600">
                      {org.username}
                    </p>

                  </div>
                </div>

                <div className="flex items-center gap-2">

                  {!org.isDefault && (
                    <button
                      type="button"
                      onClick={() => onSetDefault(org.id)}
                      className="h-8 rounded-lg border border-slate-200 px-3 text-[11px] font-medium text-slate-600 transition hover:border-blue-200 hover:text-blue-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-blue-500/30 dark:hover:text-blue-400"
                    >
                      Set default
                    </button>
                  )}

                  <button
                    type="button"
                    className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
                    title="Organization options"
                  >
                    <MoreHorizontal size={16} />
                  </button>

                  <button
                    type="button"
                    onClick={() => onDisconnect(org.id)}
                    className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-100 text-red-400 transition hover:bg-red-50 hover:text-red-600 dark:border-red-500/20 dark:hover:bg-red-500/10"
                    title="Disconnect"
                  >
                    <Trash2 size={15} />
                  </button>

                </div>

              </div>

            </div>
          ))}

        </div>
      )}

      {/* Environment Information */}

      <Card
        title="Environment management"
        description="ApexAI can work with multiple Salesforce environments."
        icon={Globe2}
      >
        <div className="grid gap-3 sm:grid-cols-3">

          <EnvironmentCard
            title="Production"
            description="Live Salesforce environment"
          />

          <EnvironmentCard
            title="UAT"
            description="User acceptance testing"
          />

          <EnvironmentCard
            title="Sandbox"
            description="Development and testing"
          />

        </div>
      </Card>

    </div>
  );
}

function EnvironmentCard({ title, description }) {
  return (
    <div className="rounded-xl border border-slate-200 p-4 dark:border-zinc-800">

      <div className="flex items-center gap-2">

        <div className="h-2 w-2 rounded-full bg-emerald-500" />

        <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
          {title}
        </p>

      </div>

      <p className="mt-2 text-[10px] leading-4 text-slate-500 dark:text-zinc-500">
        {description}
      </p>

    </div>
  );
}

/* =========================================================
   MEMBERS
========================================================= */

function MembersTab({ members, setMembers }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Builder");

  function addMember() {
    if (!email.trim()) return;

    const name = email
      .split("@")[0]
      .replace(/[._-]/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());

    const initials = name
      .split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2);

    setMembers((current) => [
      ...current,
      {
        id: Date.now(),
        name,
        email,
        role,
        status: "Active",
        initials,
        you: false,
      },
    ]);

    setEmail("");
  }

  function removeMember(id) {
    setMembers((current) =>
      current.filter((member) => member.id !== id)
    );
  }

  function updateRole(id, newRole) {
    setMembers((current) =>
      current.map((member) =>
        member.id === id
          ? { ...member, role: newRole }
          : member
      )
    );
  }

  return (
    <div className="space-y-5">

      {/* Add Member */}

      <Card
        title="Add member"
        description="Add an existing ApexAI user to this workspace."
        icon={UserPlus}
      >
        <div className="space-y-4">

          <div>
            <label className="mb-1.5 block text-[11px] font-medium text-slate-600 dark:text-zinc-400">
              Email
            </label>

            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="user@company.com"
              className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white dark:placeholder:text-zinc-600"
            />
          </div>

          <div>
            <label className="mb-2 block text-[11px] font-medium text-slate-600 dark:text-zinc-400">
              Role
            </label>

            <div className="flex flex-wrap gap-2">

              {roles.map((item) => (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => setRole(item.name)}
                  className={[
                    "rounded-lg border px-3 py-1.5 text-[10px] font-medium transition",
                    role === item.name
                      ? "border-blue-300 bg-blue-50 text-blue-600 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-400"
                      : "border-slate-200 text-slate-500 hover:border-slate-300 dark:border-zinc-700 dark:text-zinc-400",
                  ].join(" ")}
                >
                  {item.name}
                </button>
              ))}

            </div>
          </div>

          <div className="flex justify-end">

            <button
              type="button"
              onClick={addMember}
              disabled={!email.trim()}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus size={15} />
              Add member
            </button>

          </div>

        </div>
      </Card>

      {/* Members */}

      <Card
        title={`Members (${members.length})`}
        description="Manage workspace access and member roles."
        icon={Users}
      >
        <div className="divide-y divide-slate-100 dark:divide-zinc-800">

          {members.map((member) => (
            <div
              key={member.id}
              className="flex flex-col gap-4 py-4 first:pt-0 last:pb-0 lg:flex-row lg:items-center lg:justify-between"
            >

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50 text-[10px] font-semibold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                  {member.initials}
                </div>

                <div>

                  <div className="flex items-center gap-2">

                    <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
                      {member.name}
                    </p>

                    {member.you && (
                      <span className="rounded-full bg-purple-50 px-1.5 py-0.5 text-[9px] text-purple-500 dark:bg-purple-500/10">
                        You
                      </span>
                    )}

                  </div>

                  <p className="mt-0.5 text-[10px] text-slate-500 dark:text-zinc-500">
                    {member.email}
                  </p>

                </div>

              </div>

              <div className="flex items-center gap-2">

                <Badge variant="success" dot>
                  {member.status}
                </Badge>

                <div className="relative">

                  <select
                    value={member.role}
                    onChange={(event) =>
                      updateRole(member.id, event.target.value)
                    }
                    className="h-8 appearance-none rounded-lg border border-slate-200 bg-white pl-3 pr-7 text-[10px] font-medium text-slate-600 outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                  >
                    {roles.map((item) => (
                      <option
                        key={item.name}
                        value={item.name}
                      >
                        {item.name}
                      </option>
                    ))}
                  </select>

                  <ChevronDown
                    size={12}
                    className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400"
                  />

                </div>

                {!member.you && (
                  <button
                    type="button"
                    onClick={() => removeMember(member.id)}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10"
                  >
                    <Trash2 size={14} />
                  </button>
                )}

              </div>

            </div>
          ))}

        </div>
      </Card>

    </div>
  );
}

/* =========================================================
   GOVERNANCE
========================================================= */

function GovernanceTab() {
  const [selfApproval, setSelfApproval] = useState(false);

  return (
    <div className="space-y-5">

      {/* Self approval */}

      <Card
        title="Promotion governance"
        description="Control how implementation plans are approved and released."
        icon={ShieldCheck}
      >
        <div className="flex items-center justify-between gap-5">

          <div>

            <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
              Self-approval for promotions
            </p>

            <p className="mt-1 max-w-2xl text-[10px] leading-4 text-slate-500 dark:text-zinc-500">
              When enabled, the person who created a promotion request
              can also approve it. For larger teams, keeping this disabled
              provides an additional approval step.
            </p>

          </div>

          <button
            type="button"
            onClick={() => setSelfApproval(!selfApproval)}
            className={[
              "relative h-6 w-11 shrink-0 rounded-full transition",
              selfApproval
                ? "bg-blue-600"
                : "bg-slate-200 dark:bg-zinc-700",
            ].join(" ")}
            aria-label="Toggle self approval"
          >
            <span
              className={[
                "absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition",
                selfApproval
                  ? "left-6"
                  : "left-1",
              ].join(" ")}
            />
          </button>

        </div>
      </Card>

      {/* Roles */}

      <Card
        title="Roles & what they can do"
        description="Reference for workspace permissions. Roles are additive."
        icon={LockKeyhole}
      >
        <div className="space-y-2">

          {roles.map((role) => (
            <div
              key={role.name}
              className="flex flex-col gap-2 rounded-lg border border-slate-200 px-3 py-3 sm:flex-row sm:items-center dark:border-zinc-800"
            >

              <span className="w-fit rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[9px] font-semibold text-blue-600 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-400">
                {role.name}
              </span>

              <p className="text-[10px] leading-4 text-slate-500 dark:text-zinc-500">
                {role.description}
              </p>

            </div>
          ))}

        </div>
      </Card>

      {/* Workspace */}

      <Card
        title="Workspace"
        description="Basic information about this ApexAI workspace."
        icon={Settings2}
      >
        <div className="grid gap-5 sm:grid-cols-2">

          <InfoItem
            label="Workspace name"
            value="Acme Corp ApexAI Workspace"
          />

          <InfoItem
            label="Workspace tier"
            value="Professional"
          />

          <InfoItem
            label="Workspace ID"
            value="apexai-acme-production"
          />

          <InfoItem
            label="Created"
            value="18 August 2026"
          />

        </div>
      </Card>

    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div>

      <p className="text-[9px] font-medium uppercase tracking-wide text-slate-400 dark:text-zinc-600">
        {label}
      </p>

      <p className="mt-1 text-xs font-medium text-slate-800 dark:text-zinc-200">
        {value}
      </p>

    </div>
  );
}

/* =========================================================
   GIT
========================================================= */

function GitTab() {
  const [connected, setConnected] = useState(false);

  return (
    <div className="space-y-5">

      <Card
        title="Git integration"
        description="Connect a repository to import implementation plans and Salesforce source."
        icon={GitBranch}
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">

          <div className="flex items-start gap-4">

            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-200">
              {/* GitHub icon replaced with GitBranch
                  because GitHub is unavailable in the installed lucide-react version */}
              <GitBranch size={21} />
            </div>

            <div>

              <div className="flex items-center gap-2">

                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  GitHub
                </p>

                {connected ? (
                  <Badge variant="success" dot>
                    Connected
                  </Badge>
                ) : (
                  <Badge variant="warning" dot>
                    Not connected
                  </Badge>
                )}

              </div>

              <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
                Import code, implementation plans and repository context.
              </p>

            </div>

          </div>

          <button
            type="button"
            onClick={() => setConnected(!connected)}
            className={[
              "inline-flex h-9 items-center justify-center gap-2 rounded-lg px-4 text-xs font-semibold transition",
              connected
                ? "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                : "bg-blue-600 text-white hover:bg-blue-700",
            ].join(" ")}
          >

            {connected ? (
              <>
                <RefreshCw size={14} />
                Reconfigure
              </>
            ) : (
              <>
                <GitBranch size={14} />
                Connect GitHub
              </>
            )}

          </button>

        </div>
      </Card>

      {connected && (
        <Card
          title="Repository configuration"
          description="Configure the repository ApexAI should use."
          icon={GitBranch}
        >
          <div className="grid gap-4 sm:grid-cols-2">

            <ConfigField
              label="Repository"
              value="acme-corp/salesforce-platform"
            />

            <ConfigField
              label="Branch"
              value="main"
            />

            <ConfigField
              label="Default path"
              value="/salesforce"
            />

            <ConfigField
              label="Sync mode"
              value="Manual"
            />

          </div>

          <div className="mt-5 flex justify-end">

            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700"
            >
              <Save size={14} />
              Save configuration
            </button>

          </div>
        </Card>
      )}

      <Card
        title="Git workflow"
        description="How Git works with the ApexAI workspace."
        icon={ExternalLink}
      >
        <div className="space-y-3">

          <WorkflowItem
            number="01"
            title="Connect repository"
            description="Connect your GitHub repository to ApexAI."
          />

          <WorkflowItem
            number="02"
            title="Import context"
            description="Import existing Salesforce source and implementation plans."
          />

          <WorkflowItem
            number="03"
            title="Build with AI"
            description="Use repository context while creating implementation plans."
          />

        </div>
      </Card>

    </div>
  );
}

function ConfigField({ label, value }) {
  return (
    <div>

      <label className="mb-1.5 block text-[10px] font-medium text-slate-500 dark:text-zinc-500">
        {label}
      </label>

      <input
        value={value}
        readOnly
        className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 outline-none dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300"
      />

    </div>
  );
}

function WorkflowItem({ number, title, description }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 dark:border-zinc-800">

      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-[9px] font-semibold text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
        {number}
      </span>

      <div>

        <p className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
          {title}
        </p>

        <p className="mt-0.5 text-[10px] text-slate-500 dark:text-zinc-500">
          {description}
        </p>

      </div>

    </div>
  );
}

/* =========================================================
   CONNECT ORGANIZATION MODAL
========================================================= */

function ConnectOrgModal({ onClose, onConnect }) {
  const [name, setName] = useState("");
  const [environment, setEnvironment] = useState("Production");
  const [username, setUsername] = useState("");

  function handleConnect() {
    if (!name.trim() || !username.trim()) return;

    onConnect({
      name,
      environment,
      apiVersion: "v60.0",
      username,
      isDefault: false,
    });
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/30 px-4 backdrop-blur-sm">

      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-900">

        {/* Header */}

        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-zinc-800">

          <div>

            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
              Connect Salesforce Org
            </h2>

            <p className="mt-1 text-[10px] text-slate-500 dark:text-zinc-500">
              Add a Salesforce environment to ApexAI.
            </p>

          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-zinc-800 dark:hover:text-white"
          >
            <X size={16} />
          </button>

        </div>

        {/* Body */}

        <div className="space-y-4 p-5">

          <div>

            <label className="mb-1.5 block text-[10px] font-medium text-slate-600 dark:text-zinc-400">
              Organization name
            </label>

            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Acme Corp UAT"
              className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white"
            />

          </div>

          <div>

            <label className="mb-1.5 block text-[10px] font-medium text-slate-600 dark:text-zinc-400">
              Environment
            </label>

            <select
              value={environment}
              onChange={(event) =>
                setEnvironment(event.target.value)
              }
              className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white"
            >
              <option>Production</option>
              <option>UAT</option>
              <option>Sandbox</option>
              <option>Development</option>
            </select>

          </div>

          <div>

            <label className="mb-1.5 block text-[10px] font-medium text-slate-600 dark:text-zinc-400">
              Salesforce username
            </label>

            <input
              value={username}
              onChange={(event) =>
                setUsername(event.target.value)
              }
              placeholder="admin@company.com"
              className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white"
            />

          </div>

          <div className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 dark:border-blue-500/20 dark:bg-blue-500/5">

            <AlertCircle
              size={14}
              className="mt-0.5 shrink-0 text-blue-500"
            />

            <p className="text-[10px] leading-4 text-blue-700 dark:text-blue-400">
              In the production application, this action will start the
              Salesforce OAuth connection flow. This demo adds the
              organization locally.
            </p>

          </div>

        </div>

        {/* Footer */}

        <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4 dark:border-zinc-800">

          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-lg border border-slate-200 px-4 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleConnect}
            disabled={!name.trim() || !username.trim()}
            className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Cloud size={14} />
            Connect Org
          </button>

        </div>

      </div>

    </div>
  );
}

export default Admin;