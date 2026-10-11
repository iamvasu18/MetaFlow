import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { RefreshCw, Cloud, AlertCircle, Clock3 } from 'lucide-react';
import { useOrg } from '../context/OrgContext';
import { apiRequest } from '../services/workspaceApi';

const tabs = [
  { label: 'Overview', path: '/dashboard/overview' },
  { label: 'Licenses & Users', path: '/dashboard/licenses' },
  { label: 'Limits & Storage', path: '/dashboard/limits' },
  { label: 'Metadata', path: '/dashboard/metadata' },
];
export default function Dashboard() {
  const { activeOrg, loading: orgLoading } = useOrg();
  const orgId = activeOrg?.id || '';
  const [view, setView] = useState({ orgId: '', data: null, loading: false, error: '' });
  const sequence = useRef(0);
  const running = useRef('');
  const lastAttempt = useRef(0);
  const refresh = useCallback(async (force = false) => {
    if (!orgId || running.current === orgId) return;
    const request = ++sequence.current;
    running.current = orgId; lastAttempt.current = Date.now();
    setView(previous => ({ orgId, data: previous.orgId === orgId ? previous.data : null, loading: true, error: '' }));
    try {
      const path = `/orgs/${encodeURIComponent(orgId)}/intelligence${force ? '/sync' : ''}`;
      const data = await apiRequest('default', path, { method: force ? 'POST' : 'GET' });
      if (sequence.current === request) setView({ orgId, data, loading: false, error: '' });
    } catch (failure) {
      if (sequence.current === request) setView(previous => ({ ...previous, loading: false, error: failure.message }));
    } finally { if (sequence.current === request) running.current = ''; }
  }, [orgId]);
  const cancelRequests = useCallback(() => { sequence.current++; running.current = ''; }, []);
  useEffect(() => {
    let alive = true;
    Promise.resolve().then(() => { if (alive) refresh(); });
    const poll = () => { if (!document.hidden && Date.now() - lastAttempt.current >= 60000) refresh(); };
    const timer = window.setInterval(poll, 300000);
    window.addEventListener('focus', poll);
    return () => { alive = false; cancelRequests(); window.clearInterval(timer); window.removeEventListener('focus', poll); };
  }, [refresh, cancelRequests]);
  const state = view.orgId === orgId ? view : { data: null, loading: Boolean(orgId), error: '' };
  const data = state.data;
  const warnings = data ? Object.entries(data.warnings || {}) : [];
  return <div className="min-h-[calc(100vh-56px)] bg-slate-50/50 dark:bg-zinc-950">
    <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95"><div className="mx-auto max-w-[1600px] px-5 pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-widest text-blue-600">Org intelligence</p><h1 className="mt-1 text-xl font-semibold">Your Salesforce org at a glance</h1><p className="mt-1 text-xs text-slate-500">{data?.organization.name || activeOrg?.name || 'Connect an org to get started'} · Refreshes every 5 minutes while this page is open</p></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">{data ? `Synced ${new Date(data.syncedAt * 1000).toLocaleString()}` : 'Not synced yet'}</span><button type="button" onClick={() => refresh(true)} disabled={!orgId || state.loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"><RefreshCw size={14} className={state.loading ? 'animate-spin' : ''} />{state.loading ? 'Syncing…' : 'Sync now'}</button></div></div>
      <nav className="mt-5 flex gap-6 overflow-x-auto" aria-label="Org intelligence sections">{tabs.map(tab => <NavLink key={tab.path} to={tab.path} className={({ isActive }) => `whitespace-nowrap border-b-2 pb-3 text-xs font-medium ${isActive ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'}`}>{tab.label}</NavLink>)}</nav>
    </div></div>
    <div className="mx-auto max-w-[1600px] space-y-4 px-5 py-5">
      {state.error && <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950"><AlertCircle size={18} /><div>{state.error}{data && <p className="mt-1 text-xs">Showing the previous snapshot. These readings may be out of date.</p>}<Link to="/settings" className="mt-2 block underline">Manage Salesforce connections</Link></div></div>}
      {!orgId ? <div className="rounded-xl border border-dashed border-slate-300 p-12 text-center"><Cloud className="mx-auto text-blue-500" /><h2 className="mt-3 font-semibold">Connect Salesforce to see live intelligence</h2><Link to="/settings" className="mt-3 inline-block text-sm text-blue-600">Open connections</Link></div> : !data ? <div role="status" className="rounded-xl border border-slate-200 bg-white p-10 text-center dark:bg-zinc-900"><Clock3 className="mx-auto text-blue-500" /><p className="mt-3 text-sm">{state.loading || orgLoading ? 'Reading your Salesforce org…' : 'No snapshot available. Use Sync now to retry.'}</p></div> : <>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500"><span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700 dark:bg-blue-950">{data.organization.environment}</span><span>Salesforce {data.organization.apiVersion}</span><span>· {data.organization.id}</span></div>
        {warnings.length > 0 && <details className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800 dark:bg-amber-950"><summary className="cursor-pointer font-semibold">{warnings.length} metrics unavailable — other readings are live</summary><ul className="mt-3 space-y-2">{warnings.map(([key, message]) => <li key={key}><strong>{key}</strong>: {message}</li>)}</ul></details>}
        <Outlet context={{ data, refresh, loading: state.loading }} />
      </>}
    </div>
  </div>;
}
