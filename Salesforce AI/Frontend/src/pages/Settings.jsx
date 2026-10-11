import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import SalesforceConnection from '../components/SalesforceConnection';
import IntegrationSettings from '../components/IntegrationSettings';

export default function Settings() {
  const { user } = useAuth();
  return <main className="min-h-[calc(100vh-64px)] bg-slate-50 px-4 py-8 dark:bg-zinc-950"><div className="mx-auto max-w-6xl"><p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Configuration</p><h1 className="mt-2 text-2xl font-semibold">Your account and integrations</h1><p className="mt-2 text-sm text-slate-500">Connect Salesforce, choose the AI model, and bring Jira requirements into your workspace.</p><nav className="my-6 flex flex-wrap gap-3 text-sm"><a className="rounded-lg border border-slate-200 px-4 py-2 dark:border-zinc-700" href="#salesforce">Salesforce</a><a className="rounded-lg border border-slate-200 px-4 py-2 dark:border-zinc-700" href="#ai">AI provider</a><a className="rounded-lg border border-slate-200 px-4 py-2 dark:border-zinc-700" href="#jira">Jira</a></nav><div className="grid items-start gap-6 lg:grid-cols-2"><div className="space-y-5"><section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900"><h2 className="font-semibold">Account</h2><p className="mt-2 text-sm">{user?.name}</p><p className="mt-1 text-sm text-slate-500">{user?.email}</p><Link className="mt-4 inline-block text-sm text-blue-600" to="/profile">View profile</Link></section><div id="salesforce"><SalesforceConnection /></div></div><IntegrationSettings /></div></div></main>;
}
