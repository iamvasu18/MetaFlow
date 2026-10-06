import { useState } from "react";

import {
  User,
  LockKeyhole,
  Cloud,
  Database,
  GitBranch,
  Sparkles,
  Ticket,
  ChevronDown,
  CheckCircle2,
  Plus,
  Trash2,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Zap,
  HardDrive,
  Eye,
  EyeOff,
} from "lucide-react";

/* ========================================================= */
/* INITIAL STATE */
/* ========================================================= */

const initialSections = {
  account: false,
  salesforce: true,
  jira: false,
  git: false,
  ai: false,
  credits: false,
  storage: false,
};

/* ========================================================= */
/* SETTINGS */
/* ========================================================= */

function Settings() {
  const [sections, setSections] = useState(initialSections);

  /* ------------------------------------------------------- */
  /* Salesforce */
  /* ------------------------------------------------------- */

  const [salesforceMethod, setSalesforceMethod] =
    useState("connected-app");

  const [salesforceConnected, setSalesforceConnected] =
    useState(false);

  const [testingSalesforce, setTestingSalesforce] =
    useState(false);

  const [salesforceMessage, setSalesforceMessage] =
    useState("");

  const [showSecret, setShowSecret] = useState(false);

  const [orgName, setOrgName] = useState("");
  const [orgType, setOrgType] = useState("Production");
  const [username, setUsername] = useState("");
  const [consumerKey, setConsumerKey] = useState("");
  const [consumerSecret, setConsumerSecret] = useState("");

  /* ------------------------------------------------------- */
  /* Git */
  /* ------------------------------------------------------- */

  const [gitCredentials, setGitCredentials] = useState([
    {
      id: 1,
      name: "Vasu GitHub",
      username: "@iamvasu18",
      provider: "GitHub",
      connected: true,
      updated: "18/6/2026",
    },
  ]);

  const [showGitForm, setShowGitForm] = useState(false);

  /* ------------------------------------------------------- */
  /* Jira */
  /* ------------------------------------------------------- */

  const [jiraConnected, setJiraConnected] = useState(true);

  /* ------------------------------------------------------- */
  /* AI */
  /* ------------------------------------------------------- */

  const [aiConnected, setAiConnected] = useState(true);

  const [aiProvider, setAiProvider] =
    useState("Anthropic (Claude)");

  const [aiModel, setAiModel] =
    useState("claude-sonnet-4-6");

  /* ========================================================= */
  /* HANDLERS */
  /* ========================================================= */

  const toggleSection = (section) => {
    setSections((previous) => ({
      ...previous,
      [section]: !previous[section],
    }));
  };

  const testSalesforce = () => {
    setTestingSalesforce(true);
    setSalesforceMessage("");

    setTimeout(() => {
      setTestingSalesforce(false);
      setSalesforceConnected(true);

      setSalesforceMessage(
        "Connection successful. Salesforce organization is reachable."
      );
    }, 1200);
  };

  const saveSalesforce = () => {
    setSalesforceConnected(true);

    setSalesforceMessage(
      "Salesforce credentials saved successfully."
    );
  };

  const removeGitCredential = (id) => {
    setGitCredentials((credentials) =>
      credentials.filter(
        (credential) => credential.id !== id
      )
    );
  };

  /* ========================================================= */
  /* UI */
  /* ========================================================= */

  return (
    <div className="min-h-[calc(100vh-64px)] bg-slate-50 px-4 py-6 dark:bg-zinc-950 sm:px-6 lg:px-8">

      <div className="mx-auto max-w-6xl">

        {/* ================================================= */}
        {/* PAGE HEADER */}
        {/* ================================================= */}

        <div className="mb-7">

          <div className="mb-2 flex items-center gap-2 text-blue-600 dark:text-blue-400">

            <Settings2 size={17} />

            <span className="text-[11px] font-semibold uppercase tracking-[0.16em]">
              Configuration
            </span>

          </div>

          <h1 className="text-2xl font-bold tracking-tight text-slate-950 dark:text-white">
            Settings
          </h1>

          <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">
            Manage your account, integrations, AI configuration and usage.
          </p>

        </div>


        {/* ================================================= */}
        {/* TWO COLUMN SETTINGS LAYOUT */}
        {/* ================================================= */}

        <div className="grid items-start gap-5 lg:grid-cols-2">

          {/* ================================================= */}
          {/* LEFT COLUMN */}
          {/* ================================================= */}

          <div className="space-y-5">

            {/* ================================================= */}
            {/* ACCOUNT */}
            {/* ================================================= */}

            <SettingsCard
              icon={User}
              title="Account"
              subtitle="Manage your ApexAI account"
              open={sections.account}
              onClick={() => toggleSection("account")}
            >

              <div className="grid gap-4 sm:grid-cols-2">

                <InfoBox
                  label="Name"
                  value="Priya Nair"
                />

                <InfoBox
                  label="Email"
                  value="priya@acmecorp.com"
                />

              </div>

              <div className="mt-5 flex flex-wrap gap-3">

                <button className={secondaryButton}>
                  <User size={15} />
                  My Profile
                </button>

                <button className={secondaryButton}>
                  <LockKeyhole size={15} />
                  Change Password
                </button>

              </div>

            </SettingsCard>


            {/* ================================================= */}
            {/* SALESFORCE */}
            {/* ================================================= */}

            <SettingsCard
              icon={Cloud}
              title="Salesforce"
              subtitle={
                salesforceConnected
                  ? "Connected"
                  : "Not configured"
              }
              status={
                salesforceConnected
                  ? "Connected"
                  : "Not configured"
              }
              statusType={
                salesforceConnected
                  ? "success"
                  : "neutral"
              }
              open={sections.salesforce}
              onClick={() =>
                toggleSection("salesforce")
              }
            >

              {/* Connection Methods */}

              <div className="grid grid-cols-3 gap-2">

                <MethodButton
                  active={
                    salesforceMethod === "connected-app"
                  }
                  onClick={() =>
                    setSalesforceMethod(
                      "connected-app"
                    )
                  }
                >
                  Connected App

                  <span className="block text-[10px] opacity-70">
                    Recommended
                  </span>

                </MethodButton>


                <MethodButton
                  active={
                    salesforceMethod === "username"
                  }
                  onClick={() =>
                    setSalesforceMethod("username")
                  }
                >
                  Username & Password
                </MethodButton>


                <MethodButton
                  active={
                    salesforceMethod === "token"
                  }
                  onClick={() =>
                    setSalesforceMethod("token")
                  }
                >
                  Access Token
                </MethodButton>

              </div>


              {/* Salesforce Form */}

              <div className="mt-6 space-y-5">

                <div className="grid gap-5 sm:grid-cols-2">

                  <Field
                    label="Org Name"
                    value={orgName}
                    onChange={setOrgName}
                    placeholder="e.g. My Production Org"
                  />

                  <div>

                    <label className={labelClass}>
                      Org Type
                    </label>

                    <select
                      value={orgType}
                      onChange={(event) =>
                        setOrgType(
                          event.target.value
                        )
                      }
                      className={inputClass}
                    >
                      <option>
                        Production
                      </option>

                      <option>
                        Sandbox
                      </option>

                      <option>
                        UAT
                      </option>

                      <option>
                        Development
                      </option>
                    </select>

                  </div>

                </div>


                {/* Connected App */}

                {salesforceMethod ===
                  "connected-app" && (
                  <>
                    <Field
                      label="Username"
                      value={username}
                      onChange={setUsername}
                      placeholder="admin@company.com"
                    />

                    <Field
                      label="Consumer Key"
                      value={consumerKey}
                      onChange={setConsumerKey}
                      placeholder="3MVG9..."
                    />

                    <SecretField
                      label="Consumer Secret"
                      value={consumerSecret}
                      onChange={setConsumerSecret}
                      show={showSecret}
                      setShow={setShowSecret}
                    />
                  </>
                )}


                {/* Username & Password */}

                {salesforceMethod === "username" && (
                  <>
                    <Field
                      label="Username"
                      value={username}
                      onChange={setUsername}
                      placeholder="admin@company.com"
                    />

                    <SecretField
                      label="Password"
                      value={consumerSecret}
                      onChange={setConsumerSecret}
                      show={showSecret}
                      setShow={setShowSecret}
                    />

                    <Field
                      label="Security Token"
                      value=""
                      onChange={() => {}}
                      placeholder="Salesforce security token"
                    />
                  </>
                )}


                {/* Access Token */}

                {salesforceMethod === "token" && (
                  <>
                    <SecretField
                      label="Access Token"
                      value={consumerSecret}
                      onChange={setConsumerSecret}
                      show={showSecret}
                      setShow={setShowSecret}
                    />

                    <Field
                      label="Instance URL"
                      value=""
                      onChange={() => {}}
                      placeholder="https://your-org.my.salesforce.com"
                    />
                  </>
                )}


                {/* Test Admin */}

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">

                  <label className="flex cursor-pointer gap-3">

                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600"
                    />

                    <div>

                      <p className="text-sm font-medium text-slate-800 dark:text-zinc-200">
                        Use as test admin account
                      </p>

                      <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                        When running plan tests, DML
                        operations will use this
                        account's credentials instead
                        of the primary Salesforce
                        connection.
                      </p>

                    </div>

                  </label>

                </div>


                {/* Message */}

                {salesforceMessage && (
                  <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-400">

                    <CheckCircle2
                      size={16}
                      className="mt-0.5 shrink-0"
                    />

                    {salesforceMessage}

                  </div>
                )}


                {/* Actions */}

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">

                  <button
                    type="button"
                    onClick={testSalesforce}
                    disabled={testingSalesforce}
                    className={secondaryButton}
                  >

                    <RefreshCw
                      size={15}
                      className={
                        testingSalesforce
                          ? "animate-spin"
                          : ""
                      }
                    />

                    {testingSalesforce
                      ? "Testing..."
                      : "Test Connection"}

                  </button>


                  <button
                    type="button"
                    onClick={saveSalesforce}
                    className={primaryButton}
                  >
                    Save Credentials
                  </button>

                </div>

              </div>

            </SettingsCard>


            {/* ================================================= */}
            {/* GIT */}
            {/* ================================================= */}

            <SettingsCard
              icon={GitBranch}
              title="Git Providers"
              subtitle={`${gitCredentials.length} credential${
                gitCredentials.length === 1
                  ? ""
                  : "s"
              } saved`}
              open={sections.git}
              onClick={() => toggleSection("git")}
              iconColor="slate"
            >

              <div className="space-y-4">

                {gitCredentials.map(
                  (credential) => (

                    <div
                      key={credential.id}
                      className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:flex-row sm:items-center sm:justify-between"
                    >

                      <div>

                        <div className="flex flex-wrap items-center gap-2">

                          <p className="text-sm font-semibold text-slate-900 dark:text-white">
                            {credential.name}
                          </p>

                          {credential.connected && (
                            <StatusBadge>
                              Connected
                            </StatusBadge>
                          )}

                        </div>

                        <p className="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                          {credential.username}
                        </p>

                        <p className="mt-1 text-[11px] text-slate-400">
                          Updated {credential.updated}
                        </p>

                      </div>


                      <div className="flex items-center gap-1">

                        <IconButton title="Reconnect">
                          <RefreshCw size={15} />
                        </IconButton>

                        <IconButton title="Configure">
                          <Settings2 size={15} />
                        </IconButton>

                        <IconButton
                          title="Remove"
                          danger
                          onClick={() =>
                            removeGitCredential(
                              credential.id
                            )
                          }
                        >
                          <Trash2 size={15} />
                        </IconButton>

                      </div>

                    </div>

                  )
                )}


                {showGitForm ? (

                  <GitCredentialForm
                    onCancel={() =>
                      setShowGitForm(false)
                    }
                    onSave={(credential) => {

                      setGitCredentials(
                        (previous) => [
                          ...previous,
                          {
                            ...credential,
                            id: Date.now(),
                            connected: true,
                            updated:
                              "1/9/2026",
                          },
                        ]
                      );

                      setShowGitForm(false);
                    }}
                  />

                ) : (

                  <button
                    onClick={() =>
                      setShowGitForm(true)
                    }
                    className={secondaryButton}
                  >
                    <Plus size={15} />
                    Add GitHub Credential
                  </button>

                )}

              </div>

            </SettingsCard>


            {/* ================================================= */}
            {/* AI CREDIT USAGE */}
            {/* ================================================= */}

            <SettingsCard
              icon={Zap}
              title="AI Credit Usage"
              subtitle="September 2026 · Personal plan"
              open={sections.credits}
              onClick={() =>
                toggleSection("credits")
              }
              iconColor="amber"
            >

              <div className="rounded-xl border border-slate-200 p-5 dark:border-zinc-800">

                <div className="flex items-end justify-between">

                  <div>

                    <p className="text-2xl font-bold text-slate-950 dark:text-white">
                      0
                    </p>

                    <p className="text-xs text-slate-500">
                      credits used
                    </p>

                  </div>

                  <p className="text-xs text-slate-500">
                    0% of 10,000 credits
                  </p>

                </div>


                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-zinc-800">

                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{
                      width: "0%",
                    }}
                  />

                </div>


                <p className="mt-3 text-xs text-slate-500">
                  10,000 credits remaining —
                  resets at the beginning of
                  next month.
                </p>

              </div>

            </SettingsCard>

          </div>


          {/* ================================================= */}
          {/* RIGHT COLUMN */}
          {/* ================================================= */}

          <div className="space-y-5">

            {/* ================================================= */}
            {/* JIRA */}
            {/* ================================================= */}

            <SettingsCard
              icon={Ticket}
              title="Jira"
              subtitle={
                jiraConnected
                  ? "Connected"
                  : "Not configured"
              }
              status={
                jiraConnected
                  ? "Connected"
                  : "Not configured"
              }
              statusType={
                jiraConnected
                  ? "success"
                  : "neutral"
              }
              open={sections.jira}
              onClick={() =>
                toggleSection("jira")
              }
              iconColor="purple"
            >

              <div className="space-y-5">

                <div className="grid gap-5 sm:grid-cols-2">

                  <Field
                    label="Jira Site URL"
                    placeholder="https://company.atlassian.net"
                  />

                  <Field
                    label="Workspace Name"
                    placeholder="Acme Engineering"
                  />

                </div>

                <Field
                  label="Email"
                  placeholder="jira-admin@company.com"
                />

                <SecretField
                  label="API Token"
                  placeholder="Enter Jira API token"
                  show={false}
                  setShow={() => {}}
                />

                <div className="flex justify-end">

                  <button
                    onClick={() =>
                      setJiraConnected(true)
                    }
                    className={primaryButton}
                  >
                    Save & Verify
                  </button>

                </div>

              </div>

            </SettingsCard>


            {/* ================================================= */}
            {/* AI PROVIDER */}
            {/* ================================================= */}

            <SettingsCard
              icon={Sparkles}
              title="AI Provider"
              subtitle={
                aiConnected
                  ? `${aiProvider} · ${aiModel}`
                  : "Not configured"
              }
              status={
                aiConnected
                  ? "Connected"
                  : "Not configured"
              }
              statusType={
                aiConnected
                  ? "success"
                  : "neutral"
              }
              open={sections.ai}
              onClick={() =>
                toggleSection("ai")
              }
              iconColor="emerald"
            >

              <div className="space-y-5">

                <div>

                  <label className={labelClass}>
                    Provider
                  </label>

                  <select
                    value={aiProvider}
                    onChange={(event) =>
                      setAiProvider(
                        event.target.value
                      )
                    }
                    className={inputClass}
                  >
                    <option>
                      Anthropic (Claude)
                    </option>

                    <option>
                      OpenAI
                    </option>

                    <option>
                      Google Gemini
                    </option>
                  </select>

                  <p className="mt-1.5 text-[11px] text-slate-400">
                    Additional providers coming soon.
                  </p>

                </div>


                <SecretField
                  label="API Key"
                  placeholder="••••••••••••••••"
                  show={false}
                  setShow={() => {}}
                />


                <div>

                  <label className={labelClass}>
                    Model
                  </label>

                  <select
                    value={aiModel}
                    onChange={(event) =>
                      setAiModel(
                        event.target.value
                      )
                    }
                    className={inputClass}
                  >

                    <option>
                      claude-sonnet-4-6
                    </option>

                    <option>
                      claude-opus-4-1
                    </option>

                    <option>
                      gpt-5
                    </option>

                    <option>
                      gemini-2.5-pro
                    </option>

                  </select>

                </div>


                <div className="flex justify-end">

                  <button
                    onClick={() =>
                      setAiConnected(true)
                    }
                    className={primaryButton}
                  >
                    <ShieldCheck size={15} />
                    Save & Verify
                  </button>

                </div>

              </div>

            </SettingsCard>


            {/* ================================================= */}
            {/* DATA STORAGE */}
            {/* ================================================= */}

            <SettingsCard
              icon={HardDrive}
              title="Data Storage"
              subtitle="Application storage"
              open={sections.storage}
              onClick={() =>
                toggleSection("storage")
              }
              iconColor="purple"
            >

              <div className="grid gap-4 sm:grid-cols-3">

                <StorageMetric
                  label="Used"
                  value="0 GB"
                />

                <StorageMetric
                  label="Allocated"
                  value="20 GB"
                />

                <StorageMetric
                  label="Available"
                  value="20 GB"
                />

              </div>


              <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">

                <div className="flex items-start gap-3">

                  <Database
                    size={18}
                    className="mt-0.5 text-purple-500"
                  />

                  <div>

                    <p className="text-sm font-medium text-slate-800 dark:text-zinc-200">
                      Storage configuration
                    </p>

                    <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                      ApexAI application data,
                      plans and integration
                      metadata are stored securely.
                    </p>

                  </div>

                </div>

              </div>

            </SettingsCard>

          </div>

        </div>


        <div className="h-10" />

      </div>

    </div>
  );
}


/* ========================================================= */
/* SETTINGS CARD */
/* ========================================================= */

function SettingsCard({
  icon: Icon,
  title,
  subtitle,
  status,
  statusType = "neutral",
  open,
  onClick,
  children,
  iconColor = "blue",
}) {

  const iconClasses = {
    blue:
      "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",

    purple:
      "bg-purple-50 text-purple-600 dark:bg-purple-500/10 dark:text-purple-400",

    emerald:
      "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",

    amber:
      "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",

    slate:
      "bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-300",
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">

      {/* Header */}

      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-slate-50 dark:hover:bg-zinc-800/60"
      >

        <div className="flex min-w-0 items-center gap-3">

          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconClasses[iconColor]}`}
          >
            <Icon
              size={18}
              strokeWidth={1.8}
            />
          </div>


          <div className="min-w-0">

            <div className="flex flex-wrap items-center gap-2">

              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                {title}
              </h2>

              {status && (
                <StatusBadge type={statusType}>
                  {status}
                </StatusBadge>
              )}

            </div>

            <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-zinc-400">
              {subtitle}
            </p>

          </div>

        </div>


        <ChevronDown
          size={17}
          className={`shrink-0 text-slate-400 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />

      </button>


      {/* Content */}

      {open && (
        <div className="border-t border-slate-200 px-5 py-5 dark:border-zinc-800">
          {children}
        </div>
      )}

    </section>
  );
}


/* ========================================================= */
/* STATUS */
/* ========================================================= */

function StatusBadge({
  children,
  type = "success",
}) {

  const styles =
    type === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-400"
      : "border-slate-200 bg-slate-50 text-slate-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${styles}`}
    >

      <span
        className={`h-1.5 w-1.5 rounded-full ${
          type === "success"
            ? "bg-emerald-500"
            : "bg-slate-400"
        }`}
      />

      {children}

    </span>
  );
}


/* ========================================================= */
/* METHOD BUTTON */
/* ========================================================= */

function MethodButton({
  active,
  children,
  onClick,
}) {

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "min-h-[52px] rounded-xl border px-3 py-2 text-xs font-medium transition",

        active
          ? "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-500/50 dark:bg-blue-500/10 dark:text-blue-400"
          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800",
      ].join(" ")}
    >
      {children}
    </button>
  );
}


/* ========================================================= */
/* FIELD */
/* ========================================================= */

function Field({
  label,
  value = "",
  onChange = () => {},
  placeholder = "",
}) {

  return (
    <div>

      <label className={labelClass}>
        {label}
      </label>

      <input
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        className={inputClass}
      />

    </div>
  );
}


/* ========================================================= */
/* SECRET FIELD */
/* ========================================================= */

function SecretField({
  label,
  value = "",
  onChange = () => {},
  placeholder = "",
  show = false,
  setShow = () => {},
}) {

  return (
    <div>

      <label className={labelClass}>
        {label}
      </label>

      <div className="relative">

        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(event) =>
            onChange(event.target.value)
          }
          placeholder={
            placeholder || "••••••••••••"
          }
          className={`${inputClass} pr-10`}
        />

        <button
          type="button"
          onClick={() =>
            setShow(!show)
          }
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >

          {show ? (
            <EyeOff size={15} />
          ) : (
            <Eye size={15} />
          )}

        </button>

      </div>

    </div>
  );
}


/* ========================================================= */
/* INFO BOX */
/* ========================================================= */

function InfoBox({
  label,
  value,
}) {

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">

      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-sm font-medium text-slate-800 dark:text-zinc-200">
        {value}
      </p>

    </div>
  );
}


/* ========================================================= */
/* STORAGE METRIC */
/* ========================================================= */

function StorageMetric({
  label,
  value,
}) {

  return (
    <div className="rounded-xl border border-slate-200 p-4 dark:border-zinc-800">

      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="mt-1 text-xl font-bold text-slate-900 dark:text-white">
        {value}
      </p>

    </div>
  );
}


/* ========================================================= */
/* ICON BUTTON */
/* ========================================================= */

function IconButton({
  children,
  title,
  onClick,
  danger = false,
}) {

  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={[
        "flex h-8 w-8 items-center justify-center rounded-lg transition",

        danger
          ? "text-slate-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/20"
          : "text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200",
      ].join(" ")}
    >
      {children}
    </button>
  );
}


/* ========================================================= */
/* GIT FORM */
/* ========================================================= */

function GitCredentialForm({
  onCancel,
  onSave,
}) {

  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-5 dark:border-blue-900/50 dark:bg-blue-950/10">

      <div className="mb-4">

        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
          Add GitHub Credential
        </h3>

        <p className="mt-1 text-xs text-slate-500">
          Connect a GitHub account for repository imports.
        </p>

      </div>


      <div className="space-y-4">

        <Field
          label="Credential Name"
          value={name}
          onChange={setName}
          placeholder="e.g. Company GitHub"
        />

        <Field
          label="GitHub Username"
          value={username}
          onChange={setUsername}
          placeholder="iamvasu18"
        />

        <SecretField
          label="Personal Access Token"
          value={token}
          onChange={setToken}
          placeholder="ghp_••••••••••"
        />

      </div>


      <div className="mt-5 flex justify-end gap-2">

        <button
          onClick={onCancel}
          className={secondaryButton}
        >
          Cancel
        </button>

        <button
          onClick={() =>
            onSave({
              name:
                name ||
                "GitHub Credential",

              username:
                username ||
                "@github-user",

              provider: "GitHub",
            })
          }
          className={primaryButton}
        >
          Save Credential
        </button>

      </div>

    </div>
  );
}


/* ========================================================= */
/* SHARED STYLES */
/* ========================================================= */

const labelClass =
  "mb-1.5 block text-xs font-medium text-slate-700 dark:text-zinc-300";

const inputClass =
  "h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-500/10 dark:border-zinc-700 dark:bg-zinc-950 dark:text-white dark:placeholder:text-zinc-600 dark:focus:border-blue-500";

const primaryButton =
  "inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50";

const secondaryButton =
  "inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-xs font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800";


export default Settings;