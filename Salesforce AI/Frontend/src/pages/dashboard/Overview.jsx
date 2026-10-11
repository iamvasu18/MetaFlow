import { Activity, Database, HardDrive, Users, Layers, Code2, Zap, ShieldCheck } from 'lucide-react';
import Card from '../../components/ui/Card';
import { MetricGrid, Usage, amount, useIntelligence } from '../../components/dashboard/LiveMetrics';
import { relativeTime } from '../../services/homeState';

export default function Overview() {
  const { data } = useIntelligence();
  const m = data.metrics;
  const limits = m.limits || {};
  const resources = ['DailyApiRequests', 'DataStorageMB', 'FileStorageMB'].map(key => limits[key]?.percentage);
  const headroom = resources.every(value => value != null) ? Math.max(0, Math.round(100 - Math.max(...resources))) : null;
  const adoption = m.enabledUsers > 0 && m.recentUsers != null ? Math.round(m.recentUsers / m.enabledUsers * 100) : null;
  const history = data.history || [];
  return <div className="space-y-4">
    <MetricGrid items={[
      { label: 'Resource headroom', value: headroom == null ? '—' : `${headroom}%`, detail: 'Lowest remaining share of API, data and file capacity', icon: ShieldCheck },
      { label: 'API usage', value: limits.DailyApiRequests?.percentage == null ? '—' : `${limits.DailyApiRequests.percentage}%`, detail: 'Salesforce rolling daily API allocation', icon: Activity },
      { label: 'Data storage', value: limits.DataStorageMB ? `${amount(limits.DataStorageMB.used)} MB` : null, detail: 'Used data storage', icon: Database },
      { label: 'File storage', value: limits.FileStorageMB ? `${amount(limits.FileStorageMB.used)} MB` : null, detail: 'Used file storage', icon: HardDrive },
      { label: 'Enabled users', value: m.enabledUsers, detail: 'User.IsActive = true', icon: Users },
      { label: 'Login adoption', value: adoption == null ? '—' : `${adoption}%`, detail: 'Enabled users who logged in within the last 30 days', icon: Users },
      { label: 'Never logged in', value: m.neverLoggedIn, detail: 'Enabled users with no LastLoginDate', icon: Users },
      { label: 'Frozen users', value: m.frozenUsers, detail: 'UserLogin.IsFrozen = true', icon: ShieldCheck },
    ]} />
    <Card title="Capacity at a glance" description="Salesforce-reported allocations; unavailable values are not treated as zero"><div className="grid gap-3 md:grid-cols-3"><Usage title="API requests" metric={limits.DailyApiRequests} /><Usage title="Data storage" metric={limits.DataStorageMB} unit="MB" /><Usage title="File storage" metric={limits.FileStorageMB} unit="MB" /></div></Card>
    <MetricGrid items={[
      { label: 'Custom objects', value: m.customObjects?.length, detail: 'API-visible custom objects and custom settings', icon: Layers },
      { label: 'Custom fields', value: m.customFields, detail: 'Tooling API inventory', icon: Database },
      { label: 'Active flow definitions', value: m.activeFlows, detail: 'Definitions with an active version', icon: Zap },
      { label: 'Apex classes', value: m.apexClasses, detail: 'Tooling API inventory', icon: Code2 },
    ]} />
    <div className="grid gap-4 lg:grid-cols-2"><Card title="Observed API usage" description="Rolling daily usage sampled hourly over the last 24 hours; history starts with your first sync">
      {history.length < 2 ? <p className="py-8 text-center text-sm text-slate-500">{history.length ? 'First snapshot saved. More readings will appear as future syncs run.' : 'API history is unavailable until a successful limits sync.'}</p> : <div className="flex h-44 items-end gap-2" role="img" aria-label="Observed daily API usage at recorded sync times">{history.map(point => <div key={point.created} className="flex h-full min-w-0 flex-1 flex-col justify-end text-center" title={`${new Date(point.created * 1000).toLocaleString()}: ${amount(point.api_used)} / ${amount(point.api_limit)}`}><span className="mb-1 text-[10px] text-slate-500">{amount(point.api_used)}</span><div className="mx-auto w-full rounded-t bg-blue-500" style={{ height: `${Math.max(2, Math.min(100, point.api_limit > 0 ? point.api_used / point.api_limit * 100 : 0))}%` }} /><span className="mt-2 truncate text-[10px] text-slate-500">{new Date(point.created * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div>)}</div>}
    </Card><Card title="Recent MetaFlow activity" description="Actions recorded by this application for your selected org">
      {data.activity.length ? <div className="divide-y divide-slate-100 dark:divide-zinc-800">{data.activity.map(item => <div key={item.id} className="flex justify-between gap-3 py-3"><div><p className="text-xs font-medium">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.status}</p></div><span className="whitespace-nowrap text-xs text-slate-500">{relativeTime(item.created)}</span></div>)}</div> : <p className="py-8 text-center text-sm text-slate-500">No MetaFlow activity recorded for this org yet.</p>}
    </Card></div>
  </div>;
}
