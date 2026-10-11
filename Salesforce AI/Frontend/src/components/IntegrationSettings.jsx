import { useEffect, useState } from 'react';
import { Sparkles, Ticket, ShieldCheck } from 'lucide-react';
import { apiRequest } from '../services/workspaceApi';

export default function IntegrationSettings() {
  const [config, setConfig] = useState(null);
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [site, setSite] = useState('');
  const [email, setEmail] = useState('');
  const [jiraToken, setJiraToken] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    apiRequest('default', '/integrations').then(value => {
      if (!alive) return;
      setConfig(value); setModel(value.ai.model); setSite(value.jira.site); setEmail(value.jira.email);
    }).catch(failure => { if (alive) setError(failure.message); });
    return () => { alive = false; };
  }, []);
  async function save(kind) {
    if (busy) return;
    setBusy(kind); setError(''); setNotice('');
    try {
      const body = kind === 'ai' ? { model, api_key: apiKey } : { site, email, api_token: jiraToken };
      const result = await apiRequest('default', `/integrations/${kind}`, { method: 'POST', body });
      setConfig(previous => ({ ...previous, [kind]: result }));
      if (kind === 'ai') setApiKey(''); else setJiraToken('');
      setNotice(`${kind === 'ai' ? 'AI provider' : 'Jira'} verified and saved.`);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(''); }
  }
  async function remove(kind) {
    if (busy) return;
    setBusy(kind); setError(''); setNotice('');
    try {
      await apiRequest('default', `/integrations/${kind}`, { method: 'DELETE' });
      const result = await apiRequest('default', '/integrations');
      setConfig(result); setModel(result.ai.model); setSite(result.jira.site); setEmail(result.jira.email); setApiKey(''); setJiraToken('');
      setNotice(kind === 'ai' ? 'Your AI override was removed. The backend default applies.' : 'Jira connection removed.');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(''); }
  }
  const card = 'rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900';
  const input = 'mt-2 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-zinc-700 dark:bg-zinc-950';
  const button = 'rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50';
  return <div className="space-y-5">
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950">{notice}</p>}
    {!config && !error && <p role="status" className="text-sm text-slate-500">Loading integration settings…</p>}
    <section id="ai" className={card}><div className="flex items-center gap-3"><Sparkles className="text-emerald-500" /><div><h2 className="font-semibold">AI provider</h2><p className="mt-1 text-xs text-slate-500">{config?.ai.verifiedAt ? `Verified ${new Date(config.ai.verifiedAt * 1000).toLocaleString()}` : config?.ai.configured ? 'Configured on the backend · not verified here yet' : 'Not configured'}</p></div></div>
      <form onSubmit={event => { event.preventDefault(); save('ai'); }} className="mt-5 space-y-4"><label className="block text-sm">Provider<select className={input} value="anthropic" disabled><option value="anthropic">Anthropic (Claude)</option></select></label><label className="block text-sm">API key<input type="password" autoComplete="new-password" className={input} value={apiKey} disabled={Boolean(busy)} onChange={event => setApiKey(event.target.value)} placeholder={config?.ai.configured ? 'Saved — leave blank to keep the current key' : 'Enter your Anthropic API key'} /></label><label className="block text-sm">Model ID<input className={input} value={model} disabled={Boolean(busy)} required onChange={event => setModel(event.target.value)} placeholder="Enter a model ID available to your account" /></label><div className="flex flex-wrap gap-3"><button className={button} disabled={Boolean(busy) || !config}>{busy === 'ai' ? 'Verifying…' : 'Save & verify'}</button>{config?.ai.source === 'account' && <button type="button" disabled={Boolean(busy)} onClick={() => remove('ai')} className="text-sm text-red-600">Remove my override</button>}</div><p className="text-xs text-slate-500">Verified settings apply to your plan generation and AI repairs. The backend defaults remain available.</p></form>
    </section>
    <section id="jira" className={card}><div className="flex items-center gap-3"><Ticket className="text-purple-500" /><div><h2 className="font-semibold">Jira Cloud</h2><p className="mt-1 text-xs text-slate-500">{config?.jira.configured ? `Verified ${new Date(config.jira.verifiedAt * 1000).toLocaleString()} · ${config.jira.displayName}` : 'Not connected'}</p></div></div><form onSubmit={event => { event.preventDefault(); save('jira'); }} className="mt-5 space-y-4"><label className="block text-sm">Jira site<input type="url" required className={input} value={site} disabled={Boolean(busy)} onChange={event => setSite(event.target.value)} placeholder="https://your-team.atlassian.net" /></label><label className="block text-sm">Atlassian email<input type="email" required className={input} value={email} disabled={Boolean(busy)} onChange={event => setEmail(event.target.value)} /></label><label className="block text-sm">API token<input type="password" autoComplete="new-password" className={input} value={jiraToken} disabled={Boolean(busy)} onChange={event => setJiraToken(event.target.value)} placeholder={config?.jira.configured ? 'Saved — leave blank to keep the current token' : 'Enter your Jira API token'} /></label><div className="flex gap-3"><button className={button} disabled={Boolean(busy) || !config}>{busy === 'jira' ? 'Verifying…' : 'Save & verify'}</button>{config?.jira.configured && <button type="button" disabled={Boolean(busy)} onClick={() => remove('jira')} className="text-sm text-red-600">Disconnect Jira</button>}</div><p className="text-xs text-slate-500">Read your assigned issues in Workspace and use a story as the requirement.</p></form></section>
    <p className="flex items-center gap-2 text-xs text-slate-500"><ShieldCheck size={15} />Integration secrets are encrypted on the backend and are never returned to the browser.</p>
  </div>;
}
