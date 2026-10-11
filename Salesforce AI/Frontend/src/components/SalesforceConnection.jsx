import { useState } from 'react';
import { Cloud, ArrowRight, CheckCircle2, RefreshCw, AlertCircle, Trash2, ShieldCheck } from 'lucide-react';
import { useOrg } from '../context/OrgContext';

export default function SalesforceConnection() {
  const { organizations, activeOrgId, selectOrganization, connect, verifyOrganization, removeOrganization, loading, error } = useOrg();
  const [environment, setEnvironment] = useState('production');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const [removing, setRemoving] = useState('');
  async function run(key, action, redirect = false) {
    setBusy(key); setNotice(null);
    try {
      const result = await action();
      if (result?.connectionMessage) setNotice({ text: result.connectionMessage, error: result.status !== 'Connected' });
      else if (!redirect) setNotice({ text: 'Connection removed from your workspace.', error: false });
    } catch (failure) { setNotice({ text: failure.message, error: true }); }
    finally { setBusy(''); }
  }
  const button = 'rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800';
  return <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
    <div className="flex items-center gap-3"><span className="rounded-xl bg-blue-50 p-3 dark:bg-blue-950"><Cloud className="text-blue-600" size={24} /></span><div><h2 className="text-lg font-semibold">Your Salesforce connections</h2><p className="text-xs text-slate-500">{organizations.length} saved · {organizations.filter(org => org.status === 'Connected').length} last verified</p></div></div>
    <p className="mt-4 text-sm text-slate-500 dark:text-zinc-400">Choose where you build. Check live access or restore an expired session without losing the connection’s workspace history.</p>
    {(notice || error) && <p role={notice?.error || error ? 'alert' : 'status'} className={`mt-4 rounded-lg p-3 text-sm ${notice?.error || error ? 'bg-red-50 text-red-700 dark:bg-red-950' : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950'}`}>{notice?.text || error}</p>}
    {loading ? <p role="status" className="mt-4 text-sm">Loading connections…</p> : <div className="mt-5 space-y-3">
      {!organizations.length && <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center"><Cloud className="mx-auto text-slate-400" /><p className="mt-2 font-medium">Your workspace starts with an org</p><p className="mt-1 text-sm text-slate-500">Connect your development org or sandbox below.</p></div>}
      {organizations.map(org => {
        const connected = org.status === 'Connected';
        return <article key={org.id} className={`rounded-xl border p-4 ${activeOrgId === org.id ? 'border-blue-300 bg-blue-50/40 dark:bg-blue-950/20' : 'border-slate-200 dark:border-zinc-700'}`}>
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="font-semibold break-all">{org.name || 'Salesforce org'}</h3><p className="mt-1 break-all text-xs text-slate-500">{org.username}</p></div><button type="button" disabled={Boolean(busy) || activeOrgId === org.id || org.status === 'Reconnect required'} onClick={() => selectOrganization(org.id)} className={`${button} text-blue-600`}>{activeOrgId === org.id ? 'Active organization' : 'Use organization'}</button></div>
          <div className={`mt-3 flex items-center gap-2 text-xs ${connected ? 'text-emerald-600' : 'text-amber-600'}`}>{connected ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}<span>{org.status || 'Not checked'} · {org.type}</span></div>
          <p className="mt-2 break-all text-xs text-slate-500">{org.instance}</p>
          <p className="mt-1 text-xs text-slate-500">{org.checkedAt ? `Last checked ${new Date(org.checkedAt * 1000).toLocaleString()}` : 'Saved connection. Live access has not been checked.'}</p>
          {org.connectionMessage && <p className="mt-2 text-xs text-slate-500">{org.connectionMessage}</p>}
          <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={Boolean(busy)} className={`${button} flex items-center gap-2`} onClick={() => run(`verify:${org.id}`, () => verifyOrganization(org.id))}><RefreshCw size={13} className={busy === `verify:${org.id}` ? 'animate-spin' : ''} />{busy === `verify:${org.id}` ? 'Checking Salesforce…' : 'Check connection'}</button><button type="button" disabled={Boolean(busy)} className={button} onClick={() => run(`reconnect:${org.id}`, () => connect(org.type === 'Sandbox' ? 'sandbox' : 'production', org.id), true)}>Reconnect</button><button type="button" disabled={Boolean(busy)} className={`${button} flex items-center gap-2 text-red-600`} onClick={() => setRemoving(org.id)}><Trash2 size={13} />Remove</button></div>
          {removing === org.id && <div className="mt-4 rounded-lg border border-red-200 p-3"><p className="text-sm">Remove this connection from MetaFlow? Salesforce records and authorization grants stay unchanged. Reconnecting later creates a new workspace connection.</p><div className="mt-3 flex gap-2"><button type="button" className={button} disabled={Boolean(busy)} onClick={() => run(`remove:${org.id}`, async () => { await removeOrganization(org.id); setRemoving(''); })}>Remove connection</button><button type="button" className={button} disabled={Boolean(busy)} onClick={() => setRemoving('')}>Cancel</button></div></div>}
        </article>;
      })}
    </div>}
    <div className="mt-6 border-t border-slate-100 pt-5 dark:border-zinc-800"><label htmlFor="salesforce-environment" className="block text-sm font-medium">Connect an organization</label><select id="salesforce-environment" value={environment} onChange={event => setEnvironment(event.target.value)} disabled={Boolean(busy)} className="mt-3 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-zinc-700 dark:bg-zinc-950"><option value="production">Production / Developer Edition</option><option value="sandbox">Sandbox</option></select><button type="button" disabled={Boolean(busy) || loading} onClick={() => run('connect', () => connect(environment), true)} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">{busy === 'connect' ? 'Opening Salesforce…' : 'Continue to Salesforce'}<ArrowRight size={16} /></button><p className="mt-3 flex items-center gap-2 text-xs text-slate-500"><ShieldCheck size={15} />Sign in and authorize access on Salesforce’s own page.</p></div>
  </section>;
}
