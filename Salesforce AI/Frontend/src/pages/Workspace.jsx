import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bot, Cloud, Code2, FileText, MessageSquare, Plus, Send, Settings2, Sun, Moon, ShieldCheck, Upload, Pencil, Wrench, Menu, X, Ticket, Sparkles } from 'lucide-react';
import './Workspace.css';
import { useTheme } from '../context/ThemeContext';
import { useOrg } from '../context/OrgContext';
import { apiRequest } from '../services/workspaceApi';
import { waitForBackgroundJob } from '../services/backgroundJobs';
import { componentErrors } from '../services/componentPresentation';
import { canDeploy, statusText, statusLabel, conversationRequirement } from '../services/workspaceState';

const RECOVERY_KEY = 'salesforce_plan_workspace_v2';
const GENERATION_JOB_KEY = 'salesforce_generation_job_v1';
const buttonClass = 'ws-button';
function readRecovery() {
  try {
    const value = JSON.parse(localStorage.getItem(RECOVERY_KEY));
    return value && value.kind === 'default' && typeof value.id === 'string' ? value : null;
  } catch { return null; }
}

export default function Workspace() {
  const { activeOrg, organizations, selectOrganization } = useOrg();
  const location = useLocation();
  const kind = 'default';
  const { theme, toggleTheme } = useTheme();
  const [requirement, setRequirement] = useState(() => location.state?.requirement || '');
  const [bundle, setBundle] = useState(null);
  const [queuedGeneration, setQueuedGeneration] = useState(null);
  const [jobProgress, setJobProgress] = useState(null);
  const token = '';
  const [approvedHash, setApprovedHash] = useState('');
  const [repairTicket, setRepairTicket] = useState('');
  const [clarification, setClarification] = useState(null);
  const [inputMessage, setInputMessage] = useState(() => location.state?.requirement || '');
  const [conversationId, setConversationId] = useState(null);
  const [conversationOrg, setConversationOrg] = useState('');
  const visibleConversation = useRef(null);
  visibleConversation.current = conversationId;
  const [messages, setMessages] = useState([]);
  const [archivedPlan, setArchivedPlan] = useState(null);
  const composerRef = useRef(null);
  const sending = useRef(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [recovery, setRecovery] = useState(() => location.state?.restorePlan || readRecovery());
  const operationLock = useRef(false);
  const uploadRef = useRef(null);
  const [showSettings, setShowSettings] = useState(false);
  const [tab, setTab] = useState('chat');
  const [layoutChoices,setLayoutChoices]=useState([]);
  const [layoutDirty,setLayoutDirty]=useState(false);
  const [confirmDeploy,setConfirmDeploy]=useState(false);
  const [chats, setChats] = useState([]);
  const [historyError, setHistoryError] = useState('');
  const [sourceEditor, setSourceEditor] = useState(null);
  const [repairEditor, setRepairEditor] = useState(null);
  const [information, setInformation] = useState('');
  const [repairInstruction, setRepairInstruction] = useState('');
  const [activeComponent, setActiveComponent] = useState('');
  const [approving, setApproving] = useState(false);
  const [editRequest, setEditRequest] = useState(null);
  const [editText, setEditText] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [jiraStories, setJiraStories] = useState([]);
  const [jiraLoading, setJiraLoading] = useState(false);
  const [jiraError, setJiraError] = useState('');
  const [selectedComponents, setSelectedComponents] = useState([]);
  const org = activeOrg?.id || '';
  const generationInThisChat = Boolean(queuedGeneration && queuedGeneration.targetOrg === org && queuedGeneration.conversationId === conversationId);
  const sameOrg = !bundle || bundle.targetOrg === org;
  const selectedOrg = organizations.find(item => item.id === (bundle?.targetOrg || org)) || activeOrg;
  const orgName = selectedOrg && !/^00D[A-Za-z0-9]+$/.test(selectedOrg.name || '') ? selectedOrg.name : selectedOrg?.username || 'Salesforce org';
  const canRevise = bundle && !['queued', 'running', 'pending', 'unknown', 'deployed', 'rejected'].includes(bundle.state);
  const canRepair = canRevise && (bundle.state === 'failed' || Boolean(bundle.error));
  const acceptBundle = useCallback((value, implementationKind = kind, threadId = conversationId) => {
    if (!value?.id || !value.sourceHash || !value.files || !value.targetOrg) {
      throw new Error('Backend returned an incomplete package.');
    }
    setInformation('');
    setArchivedPlan(null);
    setSourceEditor(null);
    setConfirmDeploy(false);
    setClarification(null); setRepairTicket('');
    setBundle(value);
    setSelectedComponents((value.components || []).map(item => `${item.metadataType}:${item.fullName}`));
    setLayoutChoices(value.layoutOptions?.selections || []);
    setLayoutDirty(false);
    setRequirement(value.requirement || '');
    setApprovedHash(value.approvedHash || '');
    const saved = { kind: implementationKind, id: value.id, targetOrg: value.targetOrg, requirement: value.requirement };
    if (!threadId) setChats(previous => [saved, ...previous.filter(chat => chat.id !== value.id)].slice(0, 50));
    setEditRequest(null);
    setRecovery(saved);
    try { localStorage.setItem(RECOVERY_KEY, JSON.stringify(saved)); } catch { /* Storage may be disabled. */ }
  }, [conversationId, kind]);
  useEffect(() => {
    let alive = true;
    if (!org) return;
    Promise.all([apiRequest('default', `/orgs/${encodeURIComponent(org)}/conversations`), apiRequest('default', `/orgs/${encodeURIComponent(org)}/chats`)]).then(([threads, rows]) => { if (alive) { setChats([...threads, ...rows]); setHistoryError(''); } }).catch(failure => { if (alive) setHistoryError(failure.message); });
    return () => { alive = false; };
  }, [org]);
  useEffect(() => {
    if (!['queued', 'running', 'pending'].includes(bundle?.state) || !sameOrg) return;
    let alive = true;
    let timer;
    const id = bundle.id;
    async function poll() {
      if (!alive) return;
      if (operationLock.current) { timer = setTimeout(poll, 2000); return; }
      operationLock.current = true;
      try {
        const status = await apiRequest('default', `/plans/${encodeURIComponent(id)}/status`);
        if (alive) {
          setError('');
          setBundle(previous => previous?.id === id ? { ...previous, ...status } : previous);
        }
        if (!['queued', 'running', 'pending'].includes(status.state)) {
          const value = await apiRequest('default', `/plans/${encodeURIComponent(id)}`);
          if (alive) acceptBundle(value);
        } else if (alive) {
          timer = setTimeout(poll, 2000);
        }
      } catch (failure) {
        if (alive) {
          setError(`Status check failed: ${failure.message}. Tracking will resume when the backend is available.`);
          if (!failure.status || failure.status >= 500) timer = setTimeout(poll, 3000);
        }
      } finally { operationLock.current = false; }
    }
    timer = setTimeout(poll, 2000);
    return () => { alive = false; clearTimeout(timer); };
  }, [bundle?.id, bundle?.jobId, bundle?.state, sameOrg, acceptBundle]);

  useEffect(() => {
    if (!org) return;
    try {
      const saved = JSON.parse(localStorage.getItem(GENERATION_JOB_KEY));
      if (saved?.backgroundJob && saved.targetOrg === org && saved.jobId) {
        setConversationId(saved.conversationId); setConversationOrg(org);
        setRequirement(saved.requirement || ''); setQueuedGeneration(saved); setJobProgress(saved);
      }
    } catch { /* Ignore malformed local recovery data. */ }
  }, [org]);
  useEffect(() => {
    if (!queuedGeneration || queuedGeneration.targetOrg !== org) return;
    const controller = new AbortController();
    const saved = queuedGeneration;
    async function follow() {
      try {
        const result = await waitForBackgroundJob(saved, { signal: controller.signal, onProgress: value => { if (!controller.signal.aborted) setJobProgress(value); } });
        if (!controller.signal.aborted && visibleConversation.current === saved.conversationId) acceptBundle(result, 'default', saved.conversationId);
      } catch (failure) {
        if (controller.signal.aborted || visibleConversation.current !== saved.conversationId) return;
        const question = failure.detail?.code === 'CLARIFICATION_REQUIRED' ? failure.detail : null;
        setClarification(question); setRepairTicket(failure.detail?.repairTicket || '');
        if (failure.detail?.code === 'NO_CHANGE_REQUIRED') { setInformation(failure.detail.message); setError(''); }
        else setError(question ? '' : failure.message);
      } finally {
        if (!controller.signal.aborted) {
          // The worker saved its reply with the terminal job state. Do not post
          // another assistant message when this browser observes the result.
          try {
            if (saved.conversationId) {
              const thread = await apiRequest('default', `/orgs/${encodeURIComponent(org)}/conversations/${encodeURIComponent(saved.conversationId)}`);
              if (!controller.signal.aborted && visibleConversation.current === saved.conversationId) setMessages(thread.messages);
            }
          } catch (failure) { if (!controller.signal.aborted && visibleConversation.current === saved.conversationId) setHistoryError(failure.message); }
          if (!controller.signal.aborted) {
            try { localStorage.removeItem(GENERATION_JOB_KEY); } catch { /* Storage may be disabled. */ }
            setQueuedGeneration(null); setJobProgress(null);
          }
        }
      }
    }
    follow();
    return () => controller.abort();
  }, [queuedGeneration?.jobId, org, acceptBundle]);

  async function loadChat(chat, keepConversation = false) {
    if (operationLock.current) return;
    operationLock.current = true; setBusy('restore'); setError(''); setSidebarOpen(false);
    try {
      if (chat.kind === 'conversation') {
        const thread = await apiRequest('default', `/orgs/${encodeURIComponent(org)}/conversations/${encodeURIComponent(chat.id)}`);
        setConversationId(thread.id); setConversationOrg(thread.targetOrg); setMessages(thread.messages); setInputMessage('');
        setBundle(null); setApprovedHash(''); setClarification(null); setInformation('');
        const latest = thread.messages.at(-1);
        const latestPlan = [...thread.messages].reverse().find(message => message.plan_id);
        if (latestPlan && !['clarification', 'error', 'no_change'].includes(latest?.kind)) acceptBundle(await apiRequest('default', `/plans/${encodeURIComponent(latestPlan.plan_id)}`), kind, thread.id);
        if (latest?.kind === 'clarification') { setRequirement(latest.context); setClarification({ question: latest.content }); }
        else if (latest?.kind === 'no_change') { setInformation(latest.content); setRequirement(latest.context); }
        else if (latest?.kind === 'error') { setError(latest.content); setRequirement(latest.context || ''); }
      } else {
        if (!keepConversation) { setConversationId(null); setConversationOrg(''); setMessages([]); setInputMessage(''); }
        acceptBundle(await apiRequest('default', `/plans/${encodeURIComponent(chat.id)}`));
      }
    }
    catch (failure) {
      if (failure.status === 404 && chat.requirement) {
        reset(); setRequirement(chat.requirement); setInputMessage(chat.requirement); setError('Your saved requirement is loaded. The previous package is unavailable on this backend; generate a new plan to continue.');
      } else setError(failure.message);
    } finally { operationLock.current = false; setBusy(''); }
  }
  function openSourceEditor(item) {
    const base = 'force-app/main/default/';
    const [object, member] = item.fullName.split('.');
    const prefixes = { ApexClass: 'classes/', ApexTrigger: 'triggers/', Flow: 'flows/' };
    const files = Object.fromEntries(Object.entries(bundle.files).filter(([path]) => {
      if (item.metadataType === 'LightningComponentBundle') return path.startsWith(`${base}lwc/${item.fullName}/`);
      if (prefixes[item.metadataType]) return path.startsWith(`${base}${prefixes[item.metadataType]}${item.fullName}.`);
      if (item.metadataType === 'CustomObject') return path === `${base}objects/${object}/${object}.object-meta.xml`;
      const directory = item.metadataType === 'CustomField' ? 'fields' : 'validationRules';
      const suffix = item.metadataType === 'CustomField' ? 'field-meta.xml' : 'validationRule-meta.xml';
      return path === `${base}objects/${object}/${directory}/${member}.${suffix}`;
    }));
    if (!Object.keys(files).length) { setError('No editable source is available for this component.'); return; }
    setSourceEditor({ name: item.fullName, files, path: Object.keys(files)[0], hash: bundle.sourceHash });
  }
  function editPlan(componentName = '') {
    setEditRequest(componentName || 'Entire plan');
    setEditText(bundle.requirement + (componentName ? `\n\nRequested change to ${componentName}: ` : ''));
  }
  async function loadJira() {
    setTab('jira'); setJiraLoading(true); setJiraError('');
    try { setJiraStories(await apiRequest('default', '/integrations/jira/stories')); }
    catch (failure) { setJiraError(failure.message); }
    finally { setJiraLoading(false); }
  }
  const locked = Boolean(busy || queuedGeneration || ['queued', 'running', 'pending', 'unknown'].includes(bundle?.state) || !sameOrg || activeOrg?.status === 'Reconnect required');


  async function viewSavedPlan(planId) {
    if (operationLock.current) return;
    operationLock.current = true; setBusy('view');
    try { setArchivedPlan(await apiRequest('default', `/plans/${encodeURIComponent(planId)}`)); }
    catch (failure) { setError(failure.message); }
    finally { operationLock.current = false; setBusy(''); }
  }
  async function pushMessage(threadId, payload) {
    const message = await apiRequest('default', `/orgs/${encodeURIComponent(org)}/conversations/${encodeURIComponent(threadId)}/messages`, { method: 'POST', body: payload });
    setMessages(previous => [...previous, message]);
    return message;
  }
  async function reply(threadId, content, messageKind, context = '', planId = null) {
    if (!threadId) return;
    try { await pushMessage(threadId, { role: 'assistant', content, kind: messageKind, context, plan_id: planId }); }
    catch (failure) { setHistoryError(`The operation completed, but its chat reply could not be saved: ${failure.message}`); }
  }
  async function sendMessage(text = inputMessage, fresh = false) {
    if (operationLock.current || sending.current || locked || !org || !text.trim()) return;
    if (/\b(?:named|called)\s*$/i.test(text)) { composerRef.current?.focus(); return; }
    if (!fresh && conversationId && conversationOrg !== org) { setError('Start a new chat for the selected org.'); return; }
    sending.current = true; setBusy('send');
    try {
      const nextRequirement = fresh ? text.trim() : conversationRequirement(requirement, text, clarification, bundle, { continuing: Boolean(conversationId), referenceOnly: Boolean(information) });
      if (fresh) { reset(); setTab('chat'); setBusy('send'); }
      let threadId = fresh ? null : conversationId;
      if (!threadId) {
        const thread = await apiRequest('default', `/orgs/${encodeURIComponent(org)}/conversations`, { method: 'POST', body: { title: text.trim().slice(0, 300) } });
        threadId = thread.id; setConversationId(threadId); setConversationOrg(org);
        setChats(previous => [thread, ...previous]);
        if (bundle && !fresh) await pushMessage(threadId, { role: 'assistant', content: `Previous implementation: ${bundle.plan?.summary || bundle.requirement}`, kind: 'plan', plan_id: bundle.id, context: bundle.requirement });
      }
      await pushMessage(threadId, { role: 'user', content: text.trim() });
      setInputMessage(''); setRequirement(nextRequirement);
      // Previous plans remain in saved chat history; they must not appear as
      // the result of a new request that has failed or needs clarification.
      setBundle(null); setApprovedHash(''); setConfirmDeploy(false);
      setSourceEditor(null); setRepairEditor(null); setClarification(null);
      await run(!fresh && clarification ? 'clarify' : 'generate', '', nextRequirement, '', threadId);
    } catch (failure) { setError(failure.message); }
    finally { sending.current = false; setBusy(''); }
  }

  async function run(action, componentName = '', answeredRequirement = '', repairNote = repairInstruction, threadId = conversationId) {
    if (operationLock.current) return;
    operationLock.current = true;
    setBusy(action);
    setInformation('');
    setActiveComponent(componentName);
    if (action === 'approve') setApproving(true);
    setError('');
    try {
      if (action === 'generate' || action === 'fix-generation' || action === 'clarify') {
        if (!(answeredRequirement || requirement).trim() || !org) {
          setShowSettings(true);
          throw new Error('Enter a requirement and select an org.');
        }
        setApprovedHash('');
        const result = await apiRequest(kind, '/plan', { method: 'POST', token,
          body: { requirement: answeredRequirement || requirement, target_org: org, generate_files: true, job_key: crypto.randomUUID(), conversation_id: threadId, ...(action === 'fix-generation' ? { repair_error: error, ...(repairTicket ? { repair_ticket: repairTicket } : {}) } : {}) } });
        if (result.backgroundJob) {
          const tracked = { ...result, conversationId: threadId, requirement: answeredRequirement || requirement };
          try { localStorage.setItem(GENERATION_JOB_KEY, JSON.stringify(tracked)); } catch { /* Server remains authoritative. */ }
          setJobProgress(result); setQueuedGeneration(tracked);
          return;
        }
        acceptBundle(result, kind, threadId);
        await reply(threadId, result.plan?.summary || 'A new implementation draft is ready for review.', 'plan', result.requirement, result.id);
      } else if (action === 'activate-flow') {
        const result=await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}/activate-flow`, {method:'POST',body:{component_name:componentName,source_hash:bundle.sourceHash}});
        acceptBundle(result);
        const activation=result.flowActivations?.[componentName];
        await reply(threadId,activation?.message || 'Flow activation status checked.','activation',result.requirement,result.id);
      } else if (action === 'save-source') {
        acceptBundle(await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}/source`, { method: 'POST', body: { component_name: sourceEditor.name, source_hash: sourceEditor.hash, files: sourceEditor.files } }));
        setSourceEditor(null);
      } else if (action === 'repair' || action === 'revise') {
        if (!sameOrg || !canRevise) throw new Error('Select the original org and check the saved operation before revising.');
        if (action === 'repair' && !componentName && !canRepair) throw new Error('Select a component to repair.');
        const body = action === 'repair' ? { component_name: componentName, instruction: repairNote, source_hash: bundle.sourceHash } : { requirement: editText };
        const result = await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}/${action}`, { method: 'POST', body });
        acceptBundle(result);
        await reply(threadId, action === 'repair' ? 'Component source repaired. Review the changes and approve again.' : 'A revised draft is ready for review.', 'plan', result.requirement, result.id);
        setRepairEditor(null); setRepairInstruction('');
        setTab('chat');
      } else if (action === 'reject') {
        await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}/reject`, { method: 'POST', token });
        await reply(threadId, 'Plan rejected. Nothing was deployed; you can continue in this chat.', 'plan', '', bundle.id);
        setBundle(null); setApprovedHash(''); setRequirement(''); setClarification(null); setError('');
        setRecovery(null);
        try { localStorage.removeItem(RECOVERY_KEY); } catch { /* Storage may be disabled. */ }
      } else if (action === 'restore') {
        const value = await apiRequest(recovery.kind, `/plans/${encodeURIComponent(recovery.id)}`, { token });
        setApprovedHash('');
        acceptBundle(value, recovery.kind);
      } else if (action === 'review-layouts') {
        const path=`/plans/${encodeURIComponent(bundle.id)}`;
        await apiRequest(kind,`${path}/layout-selections`,{method:'POST',token,body:{snapshotId:bundle.layoutOptions.snapshotId,selections:layoutChoices}});
        acceptBundle(await apiRequest(kind,`${path}/generate-metadata`,{method:'POST',token}));
      } else {
        if (action === 'deploy' && !canDeploy(bundle, approvedHash)) throw new Error('Review and approve this package first.');
        let reviewed = bundle;
        if (action === 'approve' && selectionDirty) {
          reviewed = await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}/selection`, { method: 'POST', body: { source_hash: bundle.sourceHash, components: selectedComponents } });
          acceptBundle(reviewed);
          await reply(threadId, 'Selected components and dependencies are ready for review.', 'plan', reviewed.requirement, reviewed.id);
          if (reviewed.selectionAddedDependencies?.length) {
            setInformation(`Required dependencies retained: ${reviewed.selectionAddedDependencies.join(', ')}. Review the updated selection and approve again.`);
            return;
          }
          if (!reviewed.layoutReady) throw new Error('Complete layout choices for the selected draft before approving.');
        }
        const path = `/plans/${encodeURIComponent(reviewed.id)}`;
        const options = action === 'refresh' ? { token } : { method: 'POST', token,
          ...(['deploy','approve'].includes(action) ? { body: { approved: true, source_hash: reviewed.sourceHash } } : {}) };
        const result = await apiRequest(kind, action === 'refresh' ? path : `${path}/${action}`, options);
        acceptBundle(result);
        if (action === 'approve') {
          setBusy('validate');
          acceptBundle(await apiRequest(kind, `${path}/validate`, { method: 'POST', token }));
        }
      }
    } catch (failure) {
      if (failure.detail?.code === 'NO_CHANGE_REQUIRED') { setInformation(failure.detail.message); setClarification(null); setError(''); await reply(threadId, failure.detail.message, 'no_change', answeredRequirement || requirement); return; }
      const question = failure.detail?.code === 'CLARIFICATION_REQUIRED' ? failure.detail : null;
      setError(question ? '' : failure.message);
      setRepairTicket(failure.detail?.repairTicket || '');
      setClarification(question);
      if (['generate', 'clarify', 'fix-generation'].includes(action)) await reply(threadId, question?.question || failure.message, question ? 'clarification' : 'error', answeredRequirement || requirement);
      if (bundle && ['approve', 'deploy', 'validate', 'report'].includes(action)) {
        // A lost HTTP response does not mean Salesforce failed. Fetch durable state,
        // and block resubmission if even recovery is unavailable.
        try { acceptBundle(await apiRequest(kind, `/plans/${encodeURIComponent(bundle.id)}`, { token })); }
        catch { setBundle(previous => ({ ...previous, state: 'unknown' })); }
      }
    } finally { setApproving(false); setActiveComponent(''); operationLock.current = false; setBusy(''); }
  }

  function reset() {
    setConfirmDeploy(false);
    setConversationId(null); setConversationOrg(''); setMessages([]); setInputMessage(''); setArchivedPlan(null);
    setInformation('');
    setArchivedPlan(null);
    setSourceEditor(null); setRepairEditor(null); setRepairInstruction('');
    setBundle(null); setApprovedHash(''); setError(''); setRepairTicket(''); setClarification(null);
    setRequirement(''); setEditRequest(null); setSidebarOpen(false);
    setShowSettings(true); setTab('chat'); setLayoutChoices([]); setLayoutDirty(false);
    // Keep the previous package identifier so an in-progress job can be restored.
  }

  async function uploadRequirement(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      if (file.size > 65536) throw new Error('Use a text or Markdown file smaller than 64 KB.');
      setInputMessage(await file.text());
      setError('');
    } catch (failure) { setError(failure.message); }
  }

  function updateLayout(object,layout,enabled,sectionId) {
    setLayoutDirty(true);
    setLayoutChoices(previous => {
      const choices=previous.map(choice=>({...choice,layouts:[...choice.layouts]}));
      let choice=choices.find(item=>item.object===object);
      if (!choice) {choice={object,layouts:[]};choices.push(choice);}
      choice.layouts=choice.layouts.filter(item=>item.fullName!==layout.fullName);
      if (enabled) choice.layouts.push({fullName:layout.fullName,sectionId:sectionId ?? layout.defaultSectionId});
      return choices;
    });
  }

  const components = bundle?.components?.length
    ? bundle.components
    : bundle ? [{ metadataType: 'LightningComponentBundle', fullName: bundle.componentName }] : [];
  const selectionDirty = selectedComponents.length !== components.length;
  const approved = Boolean(bundle && approvedHash === bundle.sourceHash) && !selectionDirty;
  const layoutQuestions = (bundle?.layoutOptions?.objects || []).filter(object =>
    object.layouts.length > 1);
  const needsLayoutReview = !approved && layoutQuestions.length > 0;

  return (
    <div className={`ws-shell ws-theme-${theme}`}>
      <aside className={`ws-sidebar ${sidebarOpen ? 'ws-sidebar-open' : ''}`}>
        <div className="ws-brand"><Cloud size={22} /><strong>Workspace</strong><button className="ws-mobile-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><X size={18} /></button></div>
        <div className="ws-sidebar-body">
          <button className="ws-new" disabled={Boolean(busy)} onClick={reset}><Plus size={18} /> New Chat</button>
          <button className="ws-side-action" disabled={locked} onClick={() => uploadRef.current?.click()}><Upload size={17} /> Upload requirement</button>
          <input ref={uploadRef} hidden type="file" accept=".txt,.md" onChange={uploadRequirement} />
          <p className="ws-label">PREVIOUS CHATS</p>{busy === 'generate' && <div className="ws-history"><MessageSquare size={16} /><span>{requirement}</span></div>}
          {chats.filter(chat => chat.targetOrg === org).map(chat => <button key={chat.id} title={chat.requirement} aria-label={`Open chat: ${chat.requirement}`} className="ws-history" disabled={Boolean(busy)} onClick={() => loadChat(chat)}><MessageSquare size={16} /><span>{chat.requirement || 'Saved requirement'}</span></button>)}
          {!chats.some(chat => chat.targetOrg === org) && recovery?.targetOrg === org && <button className="ws-history" disabled={Boolean(busy)} onClick={() => loadChat(recovery)}><MessageSquare size={16} /><span>{recovery.requirement || 'Previous requirement'}</span></button>}
          {historyError && <p className="ws-muted">{historyError}</p>}
        </div>
        <div className="ws-org"><Cloud size={16} /><div><select aria-label="Target org" className="ws-input" value={org} disabled={Boolean(busy || queuedGeneration) || Boolean(conversationId)} onChange={event => selectOrganization(event.target.value)}>{organizations.map(item => <option key={item.id} value={item.id}>{!/^00D[A-Za-z0-9]+$/.test(item.name || '') ? item.name : item.username}</option>)}</select><small>Active Salesforce org</small></div></div>
      </aside>

      <main className="ws-main">{sidebarOpen && <button className="ws-drawer-overlay" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
        <header className="ws-header">
          <div className="ws-tabs"><button className="ws-mobile-toggle" aria-label="Open workspace navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
            <button className={tab === 'chat' ? 'ws-tab active' : 'ws-tab'} onClick={() => setTab('chat')}><MessageSquare size={18} /> Chat</button>
            <button className={tab === 'files' ? 'ws-tab active' : 'ws-tab'} onClick={() => setTab('files')}><Code2 size={18} /> Source files</button>
          <button className={tab === 'jira' ? 'ws-tab active' : 'ws-tab'} onClick={loadJira}><Ticket size={18} />Jira stories</button></div>
          <nav className="ws-nav"><Link to="/dashboard">Dashboard</Link><Link to="/import">Import</Link><Link to="/migration">Migration</Link><Link to="/settings" aria-label="Settings"><Settings2 size={19} /></Link><button className="ws-settings-toggle" onClick={toggleTheme} aria-label="Toggle theme">{theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}</button></nav>
        </header>

        <div className="ws-scroll">{activeOrg?.status === 'Reconnect required' && <div className="ws-error" role="alert">Salesforce access needs to be restored. <Link to="/settings#salesforce">Reconnect your org</Link></div>}
          {tab === 'jira' && <section className="ws-jira"><header><h2>Your assigned stories ({jiraStories.length})</h2><button className="ws-button secondary" disabled={jiraLoading} onClick={loadJira}>Refresh</button></header>{jiraLoading && <p role="status">Loading Jira…</p>}{jiraError && <p role="alert">{jiraError} <Link to="/settings#jira">Configure Jira</Link></p>}{jiraStories.map(story => <article key={story.key} className="ws-story"><div><div className="ws-story-tags"><a href={story.url} target="_blank" rel="noreferrer">{story.key}</a>{[story.status, story.priority, story.issueType].filter(Boolean).map((tag, index) => <span className="ws-badge" key={index}>{tag}</span>)}</div><h3>{story.summary}</h3><p>{story.description || 'No description provided.'}</p></div><button className="ws-button" disabled={locked || !org} onClick={() => sendMessage(`Jira story ${story.key}: ${story.summary}\n\n${story.description || ''}`, true)}><Code2 size={16} />Build</button></article>)}{!jiraLoading && !jiraError && !jiraStories.length && <p>No assigned Jira issues found.</p>}</section>}
          {tab === 'chat' && messages.length > 0 && <div aria-label="Conversation history">{messages.map(message => <section key={message.id} className={message.role === 'user' ? 'ws-user-message' : message.kind === 'error' ? 'ws-error' : 'ws-response'}><small>{message.role === 'user' ? 'You' : 'Assistant'}</small><p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>{message.plan_id && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => viewSavedPlan(message.plan_id)}>View saved plan</button>}</section>)}</div>}
          {!bundle && !busy && !messages.length && !clarification && !information && tab !== 'jira' && <div className="ws-empty"><div className="ws-bot"><Bot size={28} /></div><h1>What would you like to build?</h1><p>Describe your Salesforce requirement below. Review the implementation, approve it, then deploy to your org.</p><div className="ws-empty-tags"><span>Apex services</span><span>Lightning components</span><span>Salesforce validation</span></div></div>}

          {busy === 'generate' && !bundle && !messages.length && tab === 'chat' && <div className="ws-user-message"><span>You</span><p>{requirement}</p></div>}
          {bundle && tab === 'chat' && <>
            {!messages.length && <div className="ws-user-message"><span>You</span><p>{bundle.requirement}</p></div>}
            <div className="ws-assistant"><div className="ws-avatar"><Bot size={20} /></div><div className="ws-response"><p>I prepared a plan for your requirement in <strong>{orgName}</strong>.</p><p>{bundle.plan?.summary || bundle.componentName}</p><ul>{components.map(item => <li key={`${item.metadataType}:${item.fullName}`}><strong>{item.fullName}</strong> <span>— {item.metadataType}</span></li>)}</ul><p>Review the proposed changes and source files, then approve the plan. Approval starts Salesforce validation without deploying. Deploy appears immediately and becomes enabled after validation passes.</p></div></div>
          </>}

          {needsLayoutReview && <div className="ws-assistant"><div className="ws-avatar"><Bot size={20} /></div><section className="ws-response ws-layout-question">
              <h3>Where should I add the new fields?</h3>
              <p>Choose the page layouts and sections below. I’ll include your choices in the files for approval.</p>
              {layoutQuestions.map(object => <fieldset key={object.object} disabled={Boolean(busy || queuedGeneration) || approved}>
                <legend>{object.layouts.length > 1 ? `I found ${object.layouts.length} page layouts for ${object.object}. Which should I use?` : `Which section on ${object.object} should contain the new fields?`}</legend>
                {object.layouts.map(layout => {
                  const selected=layoutChoices.find(choice=>choice.object===object.object)?.layouts.find(choice=>choice.fullName===layout.fullName);
                  return <div key={layout.fullName} className="ws-plan-note">
                    <label><input type="checkbox" checked={Boolean(selected)} onChange={event=>updateLayout(object.object,layout,event.target.checked,selected?.sectionId)} /> {layout.fullName}{layout.recommended ? ' (recommended)' : ''}</label>
                    {selected && object.fields.length>0 && <select className="ws-input" aria-label={`Section for ${layout.fullName}`} value={selected.sectionId ?? ''} onChange={event=>updateLayout(object.object,layout,true,event.target.value || null)}>
                      <option value="">Select a section</option>{layout.sections.map(section=><option key={section.id} value={section.id}>{section.label}</option>)}
                    </select>}
                  </div>;
                })}
              </fieldset>)}
              {!approved && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg} onClick={()=>run('review-layouts')}>Save layout choices and update reviewed files</button>}
              {(!bundle.layoutReady || layoutDirty) && <p>Complete layout review and update the files before approving.</p>}
            </section></div>}

          {bundle && <section className="ws-plan">
            <div className="ws-plan-header"><div><h2>{bundle.componentName}</h2><p>Implementation plan · {orgName}</p></div><span className={`ws-badge ${bundle.state === 'deployed' || bundle.state === 'validated' ? 'success' : ''}`}>{statusLabel(bundle)}</span></div>
            {bundle.state !== 'deployed' && <div className="ws-selection"><span>{selectedComponents.length} of {components.length} components selected</span><div>{['Valid only', 'All', 'None'].map(choice => <button key={choice} className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !canRevise} onClick={() => setSelectedComponents(choice === 'None' ? [] : components.filter(component => choice === 'All' || !componentErrors(bundle, component).length).map(item => `${item.metadataType}:${item.fullName}`))}>{choice}</button>)}</div></div>}
            <div className="ws-components">{components.map(item => <div className="ws-component" key={`${item.metadataType}:${item.fullName}`}>{bundle.state !== 'deployed' && <input type="checkbox" aria-label={`Select ${item.fullName}`} checked={selectedComponents.includes(`${item.metadataType}:${item.fullName}`)} disabled={Boolean(busy || queuedGeneration) || !canRevise || !sameOrg} onChange={event => setSelectedComponents(previous => event.target.checked ? [...previous, `${item.metadataType}:${item.fullName}`] : previous.filter(key => key !== `${item.metadataType}:${item.fullName}`))} />}<Code2 size={20} /><div><strong>{item.fullName}</strong><small>{item.metadataType}</small>{componentErrors(bundle, item).map((message, index) => <small className="ws-log-failure" key={index}>{message}</small>)}</div><span className="ws-badge">CREATE</span>{bundle.state === 'deployed' && item.metadataType === 'Flow' && <div className="ws-component-actions"><button type="button" className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg || bundle.flowActivations?.[item.fullName]?.state === 'active'} onClick={() => run('activate-flow',item.fullName)}>{busy === 'activate-flow' && activeComponent === item.fullName ? 'Activating…' : bundle.flowActivations?.[item.fullName]?.state === 'active' ? 'Active' : ['running','unknown'].includes(bundle.flowActivations?.[item.fullName]?.state) ? 'Check activation' : 'Activate'}</button>{bundle.flowActivations?.[item.fullName]?.message && <small role="status">{bundle.flowActivations[item.fullName].message}</small>}</div>}{bundle.state !== 'deployed' && <div className="ws-component-actions"><button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg || !canRevise} onClick={() => openSourceEditor(item)}><Pencil size={14} />Edit</button><button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg || !canRevise} onClick={() => { if (canRepair) run('repair', item.fullName, '', ''); else { setRepairEditor(item.fullName); setRepairInstruction(''); } }}><Wrench size={14} />{busy === 'repair' && activeComponent === item.fullName ? 'Fixing…' : 'Fix with AI'}</button></div>}</div>)}</div>
            {bundle.operation === 'deploy' && <section className="ws-deployment" aria-live="polite"><h3>{bundle.state === 'deployed' ? `Done — ${components.length}/${components.length}` : bundle.state === 'failed' ? 'Deployment failed' : 'Deploying selected components…'}{['deployed', 'failed'].includes(bundle.state) && bundle.operationSeconds != null && ` in ${Number(bundle.operationSeconds).toFixed(1)}s`}</h3><p>{orgName} · Job {bundle.jobId || 'being submitted'}</p><div className="ws-deployment-log">{bundle.state === 'deployed' && components.map(item => <div key={`${item.metadataType}:${item.fullName}`} className="ws-log-success">✓ CREATE {item.metadataType} — {item.fullName}: deployed</div>)}{(bundle.lastResult?.result?.details?.componentFailures || []).map((failure, index) => <div key={index} className="ws-log-failure">✕ {failure.fullName || failure.fileName}: {failure.problem}</div>)}{!['deployed', 'failed'].includes(bundle.state) && <div>Waiting for Salesforce completion. Status refreshes automatically.</div>}</div><progress aria-label="Deployment progress" max="1" {...(bundle.state === 'deployed' ? { value: 1 } : {})} /></section>}
            {bundle.testClasses?.length > 0 && <p className="ws-plan-note">Tests: {bundle.testClasses.join(', ')}</p>}

            {bundle.localChecks?.warnings?.length > 0 && <pre className="ws-results">{JSON.stringify(bundle.localChecks.warnings, null, 2)}</pre>}
            {tab === 'files' && <div className="ws-files">{Object.entries(bundle.files).map(([path, source]) => <details key={path}><summary><FileText size={16} />{path}</summary><pre><code>{source}</code></pre></details>)}<details><summary>Source fingerprint</summary><pre>{bundle.sourceHash}</pre></details></div>}
            {bundle.state !== 'deployed' && <div className="ws-plan-footer">
              {canRevise && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg} onClick={() => editPlan()}><Pencil size={15} />Edit request</button>}
              {canRepair && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg} onClick={() => run('repair')}><Wrench size={15} />Fix with AI</button>}
              {!approved && !approving && bundle.state !== 'rejected' && <>
                <button className={buttonClass} disabled={Boolean(busy || queuedGeneration) || !sameOrg || !bundle.layoutReady || layoutDirty || !selectedComponents.length} onClick={() => run(approved ? 'validate' : 'approve')}><ShieldCheck size={17} />Approve</button>
                {!approved && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !sameOrg} onClick={() => run('reject')}>Reject Plan</button>}
              </>}
              {(approved || approving) && bundle.state !== 'deployed' && <button className={buttonClass} disabled={Boolean(busy || queuedGeneration) || !sameOrg || !canDeploy(bundle, approvedHash)} onClick={() => setConfirmDeploy(true)}>Deploy to {orgName}</button>}
              {busy === 'validate' && <span role="status">Validating with Salesforce. No changes are being deployed.</span>}
              {bundle.state === 'deployed' && <span className="ws-badge success">Deployment completed</span>}
              {['queued', 'pending', 'unknown', 'running'].includes(bundle.state) && <>
                {bundle.jobId && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => run('report')}>Check job status</button>}
                <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => run('refresh')}>Refresh status</button>
              </>}
            </div>}
            {confirmDeploy && <section className="ws-status ws-confirm" role="region" aria-labelledby="ws-confirm-title">
              <h3 id="ws-confirm-title">Are you sure you want to deploy?</h3>
              <p>The approved files passed validation. This will deploy them to <strong>{orgName}</strong>.</p>
              <div className="ws-plan-footer">
                <button className={buttonClass} disabled={Boolean(busy || queuedGeneration) || !sameOrg || !canDeploy(bundle, approvedHash)} onClick={() => { setConfirmDeploy(false); run('deploy'); }}>Yes, deploy</button>
                <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => setConfirmDeploy(false)}>Cancel</button>
              </div>
            </section>}
            {!sameOrg && <p className="ws-error">This package belongs to {orgName}. Select its original org before validating or deploying.</p>}
            <p className="ws-plan-note">Approval applies to all displayed files and the saved target org.</p>
          </section>}

          {bundle?.sourceChanges?.length > 0 && <section className="ws-status"><h3>Source changes · approval required</h3>{bundle.sourceChanges.map(change => <details key={change.path}><summary>{change.path}</summary><p>Before</p><pre style={{ overflow: 'auto' }}>{change.before}</pre><p>After</p><pre style={{ overflow: 'auto' }}>{change.after}</pre></details>)}<p>Source saved. Review the changes; Salesforce validation runs after approval.</p></section>}
          {archivedPlan && <section className="ws-status"><h3>Saved plan · {archivedPlan.id}</h3><p>{archivedPlan.plan?.summary}</p><p>{statusText(archivedPlan)}</p>{Object.entries(archivedPlan.files).map(([path, source]) => <details key={path}><summary>{path}</summary><pre style={{ overflow: 'auto' }}>{source}</pre></details>)}<button className="ws-button secondary" onClick={() => setArchivedPlan(null)}>Close saved plan</button></section>}
          {sourceEditor && <section className="ws-status"><h3>Edit source · {sourceEditor.name}</h3><p>Save changes, review the files, then approve again. Salesforce validation checks deployment compatibility.</p><div className="ws-plan-footer">{Object.keys(sourceEditor.files).map(path => <button key={path} className="ws-button secondary" onClick={() => setSourceEditor(previous => ({ ...previous, path }))}>{path.split('/').pop()}</button>)}</div><textarea className="ws-input ws-edit-request" style={{ minHeight: 360, fontFamily: 'monospace', width: '100%' }} spellCheck={false} aria-label={`Source ${sourceEditor.path}`} value={sourceEditor.files[sourceEditor.path]} disabled={Boolean(busy || queuedGeneration)} onChange={event => { const text = event.target.value; setSourceEditor(previous => ({ ...previous, files: { ...previous.files, [previous.path]: text } })); }} /><div className="ws-plan-footer"><button className="ws-button" disabled={Boolean(busy || queuedGeneration) || !sameOrg} onClick={() => run('save-source', sourceEditor.name)}>Save source</button><button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => setSourceEditor(null)}>Cancel</button></div></section>}
          {repairEditor && <section className="ws-status"><h3>Fix with AI · {repairEditor}</h3><p>AI will use the saved error and this component’s source. Describe any additional correction you want.</p><textarea className="ws-input ws-edit-request" aria-label="AI correction instructions" value={repairInstruction} disabled={Boolean(busy || queuedGeneration)} onChange={event => setRepairInstruction(event.target.value)} /><div className="ws-plan-footer"><button className="ws-button" disabled={Boolean(busy || queuedGeneration) || (!repairInstruction.trim() && !canRepair)} onClick={() => run('repair', repairEditor)}>{busy === 'repair' ? 'Fixing…' : 'Apply AI fix'}</button><button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => setRepairEditor(null)}>Cancel</button></div></section>}
          {editRequest && <section className="ws-status"><h3>Edit {editRequest}</h3><p>Update the requirement or describe the component change. This generates a new draft; its files need fresh approval.</p><textarea className="ws-input ws-edit-request" value={editText} disabled={Boolean(busy || queuedGeneration)} onChange={event => setEditText(event.target.value)} aria-label="Updated requirement" /><div className="ws-plan-footer"><button className="ws-button" disabled={Boolean(busy || queuedGeneration) || !editText.trim()} onClick={() => run('revise')}>Generate revised plan</button><button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration)} onClick={() => setEditRequest(null)}>Cancel</button></div></section>}
          {bundle && <section className="ws-status" aria-live="polite"><strong>{statusText(bundle)}</strong><p>Operation: {bundle.operation === 'validate' ? 'Validation' : bundle.operation === 'deploy' ? 'Deployment' : 'Plan generation'}{bundle.jobId ? ` · Job: ${bundle.jobId}` : ''}</p>{bundle.error && <p className="ws-error">{bundle.error}</p>}{bundle.lastResult?.result?.details?.componentFailures?.length > 0 && <ul className="ws-error">{bundle.lastResult.result.details.componentFailures.map((failure, index) => <li key={`${failure.fileName}:${index}`}><strong>{failure.fileName || failure.fullName}</strong>: {failure.problem}</li>)}</ul>}{bundle.nextAction && <p>{bundle.nextAction}</p>}{bundle.errorDetails && <details><summary>Technical details</summary><pre className="ws-results">{bundle.errorDetails.type}: {bundle.errorDetails.message}</pre></details>}{bundle.lastResult && <details><summary>Salesforce results, tests and coverage</summary><pre className="ws-results">{JSON.stringify(bundle.lastResult, null, 2)}</pre></details>}</section>}
          {(approving || (approved && busy === 'validate')) && <div className="ws-status" role="status">Approved · Validating with Salesforce…</div>}
          {busy && <div className="ws-status" role="status"><span className="ws-spinner" />{['generate','fix-generation'].includes(busy) ? 'Thinking…' : busy === 'repair' ? 'AI is reviewing the saved failure and generating a corrected draft…' : busy === 'revise' ? 'Generating your revised plan…' : `${busy}: waiting for Salesforce…`}</div>}
          {information && <section className="ws-status" role="status"><h3>Workspace update</h3><p>{information}</p></section>}
          {clarification && !messages.some(message => message.role === 'assistant' && message.kind === 'clarification' && message.content === clarification.question) && <div className="ws-assistant" aria-live="polite"><div className="ws-avatar"><Bot size={20} /></div><div className="ws-response"><p>{clarification.question}</p></div></div>}
          {generationInThisChat && <div className="ws-assistant" role="status"><div className="ws-avatar"><Bot size={20} /></div><div className="ws-response"><p>{jobProgress?.state === 'reconnecting' ? 'Reconnecting to your saved request…' : 'Thinking…'}</p></div></div>}
          {error && !clarification && error !== bundle?.error && <div className="ws-error" role="alert"><strong>Unable to complete the request</strong><p>{error}</p>{!bundle && !clarification && requirement.trim() && <button className="ws-button secondary" disabled={Boolean(busy || queuedGeneration) || !org || activeOrg?.status === 'Reconnect required'} onClick={() => run('fix-generation')}><Wrench size={15} />Fix with AI</button>}{!clarification && <Link className="ws-settings-toggle" to="/settings">Review connections</Link>}</div>}
        </div>

        <footer className="ws-composer-area">
          <form onSubmit={event => { event.preventDefault(); sendMessage(); }}>
            <div className="ws-composer-toolbar"><span>Automatic planning · {orgName}</span><button type="button" className="ws-settings-toggle" onClick={() => setShowSettings(value => !value)}><Settings2 size={15} /> Implementation settings</button></div>
            {showSettings && <div className="ws-settings"><Link to="/settings#salesforce">Salesforce connection</Link><Link to="/settings#ai">AI provider</Link><Link to="/settings#jira">Jira connection</Link></div>}
            <div className="ws-composer"><button type="button" aria-label="Upload text requirement" disabled={locked} onClick={() => uploadRef.current?.click()}><Upload size={19} /></button><textarea ref={composerRef} aria-label="Message" rows={2} maxLength={20000} required value={inputMessage} disabled={!org || activeOrg?.status === 'Reconnect required'} onChange={event => setInputMessage(event.target.value)} placeholder={clarification ? "Reply here, or give a complete request with a different component name…" : "Describe a requirement or add a follow-up…"} /><button className="ws-send" type="submit" aria-label="Send message" disabled={locked || !org || !inputMessage.trim()}><Send size={20} /></button></div>
            <p className="ws-composer-note">{queuedGeneration && !generationInThisChat ? 'Another chat has a pending request. You can browse chats and type here; sending becomes available when it finishes.' : ['queued', 'running', 'pending', 'unknown'].includes(bundle?.state) ? 'Check the current Salesforce operation before submitting a follow-up. You can type your next message now.' : 'Continue in this chat. Each new draft needs its own approval and validation.'}</p>
          </form>
        </footer>
      </main>
    </div>
  );
}
