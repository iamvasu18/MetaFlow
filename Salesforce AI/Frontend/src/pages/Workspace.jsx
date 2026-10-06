import {
  AlertCircle,
  ArrowLeft,
  Bot,
  Check,
  ChevronRight,
  CirclePlus,
  Code2,
  Database,
  Download,
  ExternalLink,
  FileCode2,
  FileText,
  FolderGit2,
  History,
  ListTodo,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  RefreshCw,
  Send,
  Sparkles,
  Upload,
  X,
  GitBranch,
} from "lucide-react";

import { useEffect, useRef, useState } from "react";
import dashboardData from "../data/dashboardData";

const CHAT_STORAGE_KEY = "apexai_workspace_chats";

const DEFAULT_CHATS = [
  {
    id: "demo-1",
    title: "Implement appointment validation",
    preview: "Create validation rules for appointment scheduling...",
    createdAt: "Today",
    messages: [],
  },
  {
    id: "demo-2",
    title: "Objectives Automate opportunity",
    preview: "Automate opportunity objectives and approval...",
    createdAt: "Yesterday",
    messages: [],
  },
  {
    id: "demo-3",
    title: "Build an Apex class for a Healthcare",
    preview: "Create an Apex service for healthcare records...",
    createdAt: "2 days ago",
    messages: [],
  },
  {
    id: "demo-4",
    title: "Establish the Salesforce data foundation",
    preview: "Design the Salesforce data model...",
    createdAt: "3 days ago",
    messages: [],
  },
  {
    id: "demo-5",
    title: "Review Salesforce configuration",
    preview: "Review the Salesforce configuration...",
    createdAt: "4 days ago",
    messages: [],
  },
];

function Workspace() {
  const data = dashboardData;

  const fileInputRef = useRef(null);
  const planInputRef = useRef(null);

  const [activeTab, setActiveTab] = useState("chat");

  const [chats, setChats] = useState(() => {
    try {
      const saved = localStorage.getItem(CHAT_STORAGE_KEY);
      return saved ? JSON.parse(saved) : DEFAULT_CHATS;
    } catch {
      return DEFAULT_CHATS;
    }
  });

  const [activeChatId, setActiveChatId] = useState(null);
  const [requirement, setRequirement] = useState("");
  const [messages, setMessages] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const [attachment, setAttachment] = useState(null);
  const [planUploaded, setPlanUploaded] = useState(null);

  const [showGitModal, setShowGitModal] = useState(false);
  const [gitUrl, setGitUrl] = useState("");

  const [jiraStories, setJiraStories] = useState([]);

  useEffect(() => {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chats));
  }, [chats]);

  /*
   * =========================================================
   * NEW CHAT
   * =========================================================
   */

  const handleNewChat = () => {
    const id = `chat-${Date.now()}`;

    const newChat = {
      id,
      title: "New Salesforce requirement",
      preview: "Start a new AI workspace conversation...",
      createdAt: "Just now",
      messages: [],
    };

    setChats((previous) => [newChat, ...previous]);

    setActiveChatId(id);
    setMessages([]);
    setRequirement("");
    setAttachment(null);
    setPlanUploaded(null);
    setJiraStories([]);
    setActiveTab("chat");
  };

  /*
   * =========================================================
   * OPEN EXISTING CHAT
   * =========================================================
   */

  const handleOpenChat = (chat) => {
    setActiveChatId(chat.id);
    setMessages(chat.messages || []);
    setRequirement("");
    setAttachment(null);
    setPlanUploaded(null);
    setJiraStories([]);
    setActiveTab("chat");
  };

  /*
   * =========================================================
   * ATTACHMENT
   * =========================================================
   */

  const handleAttachment = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setAttachment({
      name: file.name,
      size: file.size,
      type: file.type,
    });

    event.target.value = "";
  };

  /*
   * =========================================================
   * UPLOAD PLAN
   * =========================================================
   */

  const handleUploadPlan = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    setPlanUploaded({
      name: file.name,
      size: file.size,
      type: file.type,
    });

    setRequirement(
      `Review and implement the uploaded Salesforce implementation plan: ${file.name}`
    );

    event.target.value = "";
  };

  /*
   * =========================================================
   * IMPORT FROM GIT
   * =========================================================
   */

  const handleImportGit = () => {
    if (!gitUrl.trim()) return;

    setRequirement(
      `Review the Salesforce project imported from Git repository: ${gitUrl}`
    );

    setShowGitModal(false);
    setGitUrl("");
  };

  /*
   * =========================================================
   * GENERATE AI RESPONSE
   * =========================================================
   */

  const handleGenerate = () => {
    if (!requirement.trim() && !attachment && !planUploaded) {
      return;
    }

    setIsGenerating(true);

    const userText =
      requirement.trim() ||
      (attachment
        ? `Analyze the attached Salesforce file: ${attachment.name}`
        : `Analyze uploaded plan: ${planUploaded.name}`);

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: userText,
    };

    setMessages((previous) => [...previous, userMessage]);

    setTimeout(() => {
      const aiMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          "I analyzed your Salesforce requirement. I recommend starting with the data model, followed by automation and then any Apex or Lightning Web Component development required.",
        plan: true,
      };

      setMessages((previous) => [...previous, aiMessage]);

      setIsGenerating(false);

      createImplementationStories(userText);

      saveCurrentChat(userText, [userMessage, aiMessage]);

      setRequirement("");
      setAttachment(null);
      setPlanUploaded(null);
    }, 1100);
  };

  /*
   * =========================================================
   * SAVE CHAT
   * =========================================================
   */

  const saveCurrentChat = (title, newMessages) => {
    const id = activeChatId || `chat-${Date.now()}`;

    setActiveChatId(id);

    setChats((previous) => {
      const existing = previous.find((chat) => chat.id === id);

      if (existing) {
        return previous.map((chat) =>
          chat.id === id
            ? {
                ...chat,
                title:
                  chat.title === "New Salesforce requirement"
                    ? shortenTitle(title)
                    : chat.title,
                preview: title,
                messages: [...(chat.messages || []), ...newMessages],
              }
            : chat
        );
      }

      return [
        {
          id,
          title: shortenTitle(title),
          preview: title,
          createdAt: "Just now",
          messages: newMessages,
        },
        ...previous,
      ];
    });
  };

  /*
   * =========================================================
   * JIRA STORIES
   * =========================================================
   */

  const createImplementationStories = () => {
    setJiraStories([
      {
        id: 1,
        title: "Analyze Salesforce requirement",
        type: "Analysis",
        description:
          "Review the business requirement and identify Salesforce capabilities required.",
        status: "Ready",
      },
      {
        id: 2,
        title: "Define Salesforce data model",
        type: "Configuration",
        description:
          "Identify objects, fields, relationships and metadata changes.",
        status: "Ready",
      },
      {
        id: 3,
        title: "Implement automation",
        type: "Automation",
        description:
          "Configure Flow, validation rules, approvals and notifications.",
        status: "Ready",
      },
      {
        id: 4,
        title: "Develop Apex / LWC components",
        type: "Development",
        description:
          "Create Apex classes, triggers or Lightning Web Components where required.",
        status: "Optional",
      },
      {
        id: 5,
        title: "Test and deploy",
        type: "Deployment",
        description:
          "Create test scenarios and prepare metadata for deployment.",
        status: "Ready",
      },
    ]);
  };

  /*
   * =========================================================
   * CLEAR CHAT
   * =========================================================
   */

  const handleClearChat = () => {
    setMessages([]);
    setRequirement("");
    setAttachment(null);
    setPlanUploaded(null);
    setJiraStories([]);
  };

  const isConnected =
    data?.organization?.status === "Connected";

  return (
    <main className="h-[calc(100vh-64px)] overflow-hidden bg-white text-slate-900 dark:bg-zinc-950 dark:text-white">

      {/* =====================================================
          WORKSPACE HEADER
          IMPORTANT:
          This contains ONLY Workspace-specific controls.
          Dashboard / Import / Migration / Settings are NOT
          repeated here because they already exist globally.
      ===================================================== */}

      <div className="border-b border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex h-14 items-center justify-between px-5">

          {/* Workspace title */}

          <div className="flex items-center gap-4">

            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                <Sparkles size={17} />
              </div>

              <div>
                <p className="text-sm font-semibold">
                  Workspace
                </p>

                <p className="text-[9px] text-slate-400">
                  Salesforce AI development workspace
                </p>
              </div>
            </div>

            {/* Chat / Jira tabs */}

            <div className="ml-5 flex items-center gap-1">
              <WorkspaceTab
                active={activeTab === "chat"}
                icon={MessageSquare}
                label="Chat"
                onClick={() => setActiveTab("chat")}
              />

              <WorkspaceTab
                active={activeTab === "jira"}
                icon={ListTodo}
                label="Jira Stories"
                onClick={() => setActiveTab("jira")}
                badge={jiraStories.length || null}
              />
            </div>
          </div>

          {/* Connection indicator only */}

          <div className="hidden items-center gap-2 sm:flex">
            <span
              className={[
                "h-2 w-2 rounded-full",
                isConnected
                  ? "bg-emerald-500"
                  : "bg-amber-500",
              ].join(" ")}
            />

            <span className="text-[10px] text-slate-500">
              {isConnected
                ? data.organization.name
                : "No Salesforce connection"}
            </span>
          </div>
        </div>
      </div>

      {/* =====================================================
          MAIN WORKSPACE
      ===================================================== */}

      <div className="flex h-[calc(100vh-120px)] min-h-0 overflow-hidden">

        {/* ===================================================
            LEFT SIDEBAR
        =================================================== */}

        <aside className="hidden w-[300px] shrink-0 border-r border-slate-200 bg-white lg:block dark:border-zinc-800 dark:bg-zinc-950">

          <div className="flex h-full flex-col">

            {/* New Chat */}

            <div className="p-4">
              <button
                type="button"
                onClick={handleNewChat}
                className="flex h-11 w-full items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 text-left text-[12px] font-medium text-slate-800 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
              >
                <CirclePlus size={17} />
                <span>New Chat</span>
              </button>
            </div>

            {/* Workspace Actions */}

            <div className="px-4">

              <SidebarAction
                icon={GitBranch}
                label="Import from Git"
                onClick={() => setShowGitModal(true)}
              />

              <SidebarAction
                icon={Upload}
                label="Upload Plan"
                onClick={() =>
                  planInputRef.current?.click()
                }
              />

              <input
                ref={planInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt,.md,.json"
                className="hidden"
                onChange={handleUploadPlan}
              />
            </div>

            {/* Divider */}

            <div className="mx-4 my-4 border-t border-slate-100 dark:border-zinc-900" />

            {/* Recent Chats */}

            <div className="min-h-0 flex-1 overflow-y-auto">

              <div className="px-5 pb-2">
                <div className="flex items-center justify-between">
                  <p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                    Recent
                  </p>

                  <History
                    size={13}
                    className="text-slate-300"
                  />
                </div>
              </div>

              <div className="space-y-1 px-2">

                {chats.length === 0 ? (
                  <div className="px-4 py-10 text-center">
                    <MessageSquare
                      size={22}
                      className="mx-auto text-slate-300"
                    />

                    <p className="mt-2 text-[10px] text-slate-400">
                      No recent chats
                    </p>
                  </div>
                ) : (
                  chats.map((chat) => (
                    <RecentChat
                      key={chat.id}
                      chat={chat}
                      active={activeChatId === chat.id}
                      onClick={() =>
                        handleOpenChat(chat)
                      }
                    />
                  ))
                )}

              </div>

              {chats.length > 5 && (
                <button
                  type="button"
                  className="mt-3 flex items-center gap-1 px-5 text-[9px] font-medium text-blue-600"
                >
                  <ChevronRight size={11} />
                  View all ({chats.length})
                </button>
              )}
            </div>

            {/* Salesforce Connection */}

            <div className="border-t border-slate-200 p-4 dark:border-zinc-800">

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">

                <div className="flex items-center justify-between">

                  <div className="flex items-center gap-2">

                    <span
                      className={[
                        "h-2 w-2 rounded-full",
                        isConnected
                          ? "bg-emerald-500"
                          : "bg-amber-500",
                      ].join(" ")}
                    />

                    <span className="text-[9px] font-medium text-slate-700 dark:text-zinc-300">
                      {isConnected
                        ? "Salesforce connected"
                        : "Salesforce not connected"}
                    </span>
                  </div>

                  {!isConnected && (
                    <button
                      type="button"
                      className="text-[8px] font-semibold text-blue-600"
                      onClick={() =>
                        window.location.href = "/settings"
                      }
                    >
                      Connect
                    </button>
                  )}
                </div>

                {isConnected && (
                  <p className="mt-1 truncate text-[8px] text-slate-400">
                    {data.organization.name}
                  </p>
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* ===================================================
            CONTENT
        =================================================== */}

        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-white dark:bg-zinc-950">

          {/* Connection warning */}

          {!isConnected && (
            <div className="mx-5 mt-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">

              <div className="flex items-center gap-2">
                <AlertCircle
                  size={15}
                  className="text-amber-500"
                />

                <p className="text-[10px] font-medium text-amber-700">
                  Connect your Salesforce org to restore
                  schema awareness and deployment capabilities.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  (window.location.href = "/settings")
                }
                className="text-[10px] font-semibold text-amber-600"
              >
                Connect Org
              </button>
            </div>
          )}

          {activeTab === "jira" ? (

            <JiraStories
              stories={jiraStories}
              onBack={() => setActiveTab("chat")}
              onGenerate={() => {
                createImplementationStories();
              }}
            />

          ) : (

            <div className="flex min-h-0 flex-1 flex-col">

              {/* =================================================
                  CHAT CONTENT
              ================================================= */}

              <div className="min-h-0 flex-1 overflow-y-auto">

                {messages.length === 0 ? (

                  <EmptyWorkspace
                    onSuggestion={(text) =>
                      setRequirement(text)
                    }
                  />

                ) : (

                  <div className="mx-auto max-w-[900px] px-6 py-8">

                    {messages.map((message) => (
                      <ChatMessage
                        key={message.id}
                        message={message}
                      />
                    ))}

                    {isGenerating && (
                      <div className="mt-6 flex items-center gap-3">

                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                          <Bot size={15} />
                        </div>

                        <div className="flex items-center gap-1.5">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-400" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-400 [animation-delay:100ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-400 [animation-delay:200ms]" />
                        </div>

                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* =================================================
                  COMPOSER
              ================================================= */}

              <div className="sticky bottom-0 z-20 shrink-0 border-t border-slate-200 bg-white/95 p-4 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/95">

                <div className="mx-auto max-w-[1000px]">

                  {/* Attachment */}

                  {(attachment || planUploaded) && (
                    <div className="mb-2 flex items-center gap-2">

                      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">

                        <FileText
                          size={13}
                          className="text-blue-500"
                        />

                        <span className="max-w-[300px] truncate text-[9px] font-medium text-slate-600">
                          {attachment?.name ||
                            planUploaded?.name}
                        </span>

                        <button
                          type="button"
                          onClick={() => {
                            setAttachment(null);
                            setPlanUploaded(null);
                          }}
                          className="text-slate-400 hover:text-red-500"
                        >
                          <X size={12} />
                        </button>

                      </div>
                    </div>
                  )}

                  {/* Input */}

                  <div className="rounded-2xl border border-slate-200 bg-white shadow-sm transition focus-within:border-blue-400 focus-within:shadow-md focus-within:ring-4 focus-within:ring-blue-500/5 dark:border-zinc-700 dark:bg-zinc-900">

                    <textarea
                      value={requirement}
                      onChange={(event) =>
                        setRequirement(event.target.value)
                      }
                      onKeyDown={(event) => {
                        if (
                          event.key === "Enter" &&
                          !event.shiftKey
                        ) {
                          event.preventDefault();
                          handleGenerate();
                        }
                      }}
                      placeholder="Describe your Salesforce requirement, or attach a BRD..."
                      rows={2}
                      className="max-h-32 min-h-[54px] w-full resize-none bg-transparent px-4 pt-3 text-[11px] leading-5 text-slate-700 outline-none placeholder:text-slate-400 dark:text-zinc-200 dark:placeholder:text-zinc-600"
                    />

                    <div className="flex items-center justify-between px-3 pb-2">

                      <div className="flex items-center gap-1">

                        <input
                          ref={fileInputRef}
                          type="file"
                          className="hidden"
                          accept=".pdf,.doc,.docx,.txt,.md,.csv"
                          onChange={handleAttachment}
                        />

                        <button
                          type="button"
                          onClick={() =>
                            fileInputRef.current?.click()
                          }
                          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                          title="Attach file"
                        >
                          <Paperclip size={14} />
                        </button>

                        <button
                          type="button"
                          onClick={() =>
                            setShowGitModal(true)
                          }
                          className="flex h-8 items-center gap-1.5 rounded-lg px-2 text-[8px] text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                        >
                          <FolderGit2 size={13} />
                          Git
                        </button>

                      </div>

                      <button
                        type="button"
                        disabled={
                          isGenerating ||
                          (!requirement.trim() &&
                            !attachment &&
                            !planUploaded)
                        }
                        onClick={handleGenerate}
                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {isGenerating ? (
                          <RefreshCw
                            size={14}
                            className="animate-spin"
                          />
                        ) : (
                          <Send size={14} />
                        )}
                      </button>
                    </div>
                  </div>

                  <p className="mt-2 text-center text-[8px] text-slate-400">
                    ApexAI can make mistakes. Review generated
                    Salesforce changes before deployment.
                  </p>

                </div>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* =====================================================
          GIT MODAL
      ===================================================== */}

      {showGitModal && (
        <GitModal
          gitUrl={gitUrl}
          setGitUrl={setGitUrl}
          onClose={() => {
            setShowGitModal(false);
            setGitUrl("");
          }}
          onImport={handleImportGit}
        />
      )}
    </main>
  );
}

/*
 * =========================================================
 * WORKSPACE TAB
 * =========================================================
 */

function WorkspaceTab({
  active,
  icon: Icon,
  label,
  onClick,
  badge,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex h-9 items-center gap-2 rounded-lg px-3 text-[11px] font-medium transition",
        active
          ? "bg-blue-50 text-blue-600"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-800",
      ].join(" ")}
    >
      <Icon size={15} />

      {label}

      {badge && (
        <span className="rounded-full bg-blue-100 px-1.5 text-[7px] text-blue-600">
          {badge}
        </span>
      )}
    </button>
  );
}

/*
 * =========================================================
 * SIDEBAR ACTION
 * =========================================================
 */

function SidebarAction({
  icon: Icon,
  label,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-[11px] font-medium text-slate-600 transition hover:bg-slate-50 hover:text-blue-600"
    >
      <Icon size={15} />
      {label}
    </button>
  );
}

/*
 * =========================================================
 * RECENT CHAT
 * =========================================================
 */

function RecentChat({
  chat,
  active,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "group flex w-full items-start gap-2 rounded-lg px-3 py-2.5 text-left transition",
        active
          ? "bg-slate-100 text-slate-900"
          : "text-slate-500 hover:bg-slate-50",
      ].join(" ")}
    >
      <MessageSquare
        size={13}
        className={[
          "mt-0.5 shrink-0",
          active
            ? "text-blue-500"
            : "text-slate-300",
        ].join(" ")}
      />

      <div className="min-w-0 flex-1">
        <p className="truncate text-[10px] font-medium">
          {chat.title}
        </p>

        <p className="mt-0.5 truncate text-[8px] text-slate-400">
          {chat.preview}
        </p>
      </div>

      <MoreHorizontal
        size={12}
        className="mt-0.5 hidden shrink-0 text-slate-300 group-hover:block"
      />
    </button>
  );
}

/*
 * =========================================================
 * EMPTY WORKSPACE
 * =========================================================
 */

function EmptyWorkspace({
  onSuggestion,
}) {
  return (
    <div className="flex min-h-[520px] items-center justify-center px-6">

      <div className="w-full max-w-[650px] text-center">

        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-blue-100 bg-blue-50 text-blue-500">
          <Bot
            size={28}
            strokeWidth={1.7}
          />
        </div>

        <h1 className="mt-6 text-[22px] font-semibold tracking-tight text-slate-700">
          What would you like to build?
        </h1>

        <p className="mx-auto mt-3 max-w-[600px] text-[12px] leading-6 text-slate-400">
          Describe your Salesforce requirement in natural
          language. ApexAI can analyze your requirement and
          create a complete implementation plan.
        </p>

        <div className="mt-7 flex flex-wrap justify-center gap-2">

          <Suggestion
            text="Create an Opportunity validation rule"
            onClick={() =>
              onSuggestion(
                "Create a validation rule for Opportunity amount over $50,000."
              )
            }
          />

          <Suggestion
            text="Build a Case management solution"
            onClick={() =>
              onSuggestion(
                "Build a Salesforce Case management solution with automated assignment and escalation."
              )
            }
          />

          <Suggestion
            text="Create an LWC dashboard"
            onClick={() =>
              onSuggestion(
                "Create a Lightning Web Component dashboard for Salesforce organization metrics."
              )
            }
          />

        </div>

        <div className="mt-8 flex items-center justify-center gap-2 text-[9px] text-slate-400">
          <Sparkles size={12} />
          AI-powered Salesforce implementation planning
        </div>

      </div>
    </div>
  );
}

/*
 * =========================================================
 * SUGGESTION
 * =========================================================
 */

function Suggestion({
  text,
  onClick,
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[9px] text-slate-500 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600"
    >
      {text}
    </button>
  );
}

/*
 * =========================================================
 * CHAT MESSAGE
 * =========================================================
 */

function ChatMessage({
  message,
}) {
  const isUser = message.role === "user";

  return (
    <div
      className={[
        "mb-7 flex gap-3",
        isUser
          ? "justify-end"
          : "justify-start",
      ].join(" ")}
    >

      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          <Bot size={15} />
        </div>
      )}

      <div
        className={[
          "max-w-[720px] rounded-xl px-4 py-3 text-[11px] leading-5",
          isUser
            ? "bg-blue-600 text-white"
            : "border border-slate-200 bg-white text-slate-600",
        ].join(" ")}
      >

        {message.content}

        {message.plan && (
          <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50/50 p-3">

            <div className="flex items-center gap-2">

              <Sparkles
                size={13}
                className="text-blue-500"
              />

              <span className="text-[9px] font-semibold text-blue-600">
                Implementation plan generated
              </span>

            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">

              <PlanItem
                icon={Database}
                title="Data Model"
              />

              <PlanItem
                icon={GitBranch}
                title="Automation"
              />

              <PlanItem
                icon={Code2}
                title="Development"
              />

              <PlanItem
                icon={Check}
                title="Testing & Deployment"
              />

            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/*
 * =========================================================
 * PLAN ITEM
 * =========================================================
 */

function PlanItem({
  icon: Icon,
  title,
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-white px-3 py-2">

      <Icon
        size={12}
        className="text-blue-500"
      />

      <span className="text-[8px] font-medium text-slate-600">
        {title}
      </span>
    </div>
  );
}

/*
 * =========================================================
 * JIRA STORIES
 * =========================================================
 */

function JiraStories({
  stories,
  onBack,
  onGenerate,
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">

      <div className="mx-auto max-w-[1000px] px-6 py-7">

        <div className="flex items-center justify-between">

          <div className="flex items-center gap-3">

            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <ListTodo size={16} />
            </div>

            <div>
              <h1 className="text-lg font-semibold text-slate-800">
                Jira Stories
              </h1>

              <p className="mt-0.5 text-[9px] text-slate-400">
                Convert your Salesforce requirement into
                implementation stories.
              </p>
            </div>

          </div>

          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1.5 text-[9px] font-medium text-blue-600"
          >
            <ArrowLeft size={12} />
            Back to Chat
          </button>

        </div>

        {stories.length === 0 ? (

          <div className="mt-8 rounded-xl border border-slate-200 bg-white p-10 text-center">

            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-slate-300">
              <ListTodo size={21} />
            </div>

            <h2 className="mt-4 text-[13px] font-semibold text-slate-700">
              No Jira stories yet
            </h2>

            <p className="mx-auto mt-2 max-w-[450px] text-[9px] leading-5 text-slate-400">
              Start a Salesforce requirement in Chat and
              ApexAI can generate implementation stories.
            </p>

            <button
              type="button"
              onClick={onGenerate}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-[9px] font-semibold text-white hover:bg-blue-700"
            >
              <Sparkles size={12} />
              Generate Stories
            </button>

          </div>

        ) : (

          <div className="mt-6 space-y-3">

            {stories.map((story) => (
              <JiraStory
                key={story.id}
                story={story}
              />
            ))}

          </div>
        )}
      </div>
    </div>
  );
}

/*
 * =========================================================
 * JIRA STORY
 * =========================================================
 */

function JiraStory({
  story,
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 transition hover:border-blue-200 hover:shadow-sm">

      <div className="flex items-start gap-4">

        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          <FileCode2 size={15} />
        </div>

        <div className="min-w-0 flex-1">

          <div className="flex flex-wrap items-center gap-2">

            <span className="text-[8px] font-semibold text-slate-400">
              APEX-{story.id}
            </span>

            <h3 className="text-[11px] font-semibold text-slate-800">
              {story.title}
            </h3>

          </div>

          <p className="mt-2 text-[9px] leading-5 text-slate-500">
            {story.description}
          </p>

          <div className="mt-3 flex items-center gap-2">

            <span className="rounded-full bg-slate-100 px-2 py-1 text-[7px] font-medium text-slate-500">
              {story.type}
            </span>

            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[7px] font-medium text-emerald-600">
              {story.status}
            </span>

          </div>
        </div>

        <button
          type="button"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-300 hover:bg-slate-50 hover:text-blue-600"
        >
          <ExternalLink size={13} />
        </button>

      </div>
    </div>
  );
}

/*
 * =========================================================
 * GIT MODAL
 * =========================================================
 */

function GitModal({
  gitUrl,
  setGitUrl,
  onClose,
  onImport,
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4 backdrop-blur-[2px]">

      <div className="w-full max-w-[520px] rounded-xl border border-slate-200 bg-white shadow-xl">

        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">

          <div className="flex items-center gap-3">

            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-50 text-slate-600">
              <FolderGit2 size={17} />
            </div>

            <div>
              <h2 className="text-[12px] font-semibold text-slate-800">
                Import from Git
              </h2>

              <p className="mt-0.5 text-[8px] text-slate-400">
                Connect a Salesforce project repository.
              </p>
            </div>

          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100"
          >
            <X size={14} />
          </button>

        </div>

        <div className="p-5">

          <label className="text-[9px] font-medium text-slate-600">
            Repository URL
          </label>

          <div className="mt-2 flex items-center rounded-lg border border-slate-200 bg-slate-50 px-3">

            <GitBranch
              size={14}
              className="text-slate-400"
            />

            <input
              value={gitUrl}
              onChange={(event) =>
                setGitUrl(event.target.value)
              }
              placeholder="https://github.com/company/salesforce-project"
              className="h-10 min-w-0 flex-1 bg-transparent px-2 text-[10px] text-slate-700 outline-none placeholder:text-slate-400"
            />

          </div>

          <div className="mt-4 rounded-lg bg-blue-50 p-3">

            <div className="flex gap-2">

              <Sparkles
                size={13}
                className="mt-0.5 shrink-0 text-blue-500"
              />

              <p className="text-[8px] leading-4 text-blue-600">
                ApexAI will use the repository as
                implementation context for your Salesforce
                requirement.
              </p>

            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-5 py-4">

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-[9px] font-medium text-slate-500 hover:bg-slate-50"
          >
            Cancel
          </button>

          <button
            type="button"
            disabled={!gitUrl.trim()}
            onClick={onImport}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-[9px] font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
          >
            <Download size={11} />
            Import Repository
          </button>

        </div>
      </div>
    </div>
  );
}

/*
 * =========================================================
 * SHORT TITLE
 * =========================================================
 */

function shortenTitle(text) {
  if (!text) {
    return "New Salesforce requirement";
  }

  const clean = text
    .replace(/\s+/g, " ")
    .trim();

  if (clean.length <= 45) {
    return clean;
  }

  return `${clean.slice(0, 45)}...`;
}

export default Workspace;