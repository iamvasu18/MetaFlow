import Card from '../../components/ui/Card';
import { MetricGrid, Usage, useIntelligence } from '../../components/dashboard/LiveMetrics';

export default function LimitsStorage() {
  const { data } = useIntelligence();
  const limits = data.metrics.limits;
  const entries = Object.entries(limits || {}).sort(([a], [b]) => a.localeCompare(b));
  return <div className="space-y-4"><MetricGrid items={[
    { label: 'Scheduled jobs', value: data.metrics.scheduledJobs, detail: 'CronTrigger records excluding completed, deleted and error states' },
    { label: 'Reported allocations', value: limits ? entries.length : null, detail: 'Numeric limits returned by Salesforce' },
    { label: 'Above 90% usage', value: limits ? entries.filter(([, value]) => value.percentage >= 90).length : null, detail: 'Review available allocation details below' },
  ]} /><Card title="Storage" description="Values are shown in MB, matching Salesforce’s Limits API"><div className="grid gap-3 md:grid-cols-2"><Usage title="Data storage" metric={limits?.DataStorageMB} unit="MB" /><Usage title="File storage" metric={limits?.FileStorageMB} unit="MB" /></div></Card>
    <Card title="Salesforce limits and allocations" description="Org-wide limits exposed by the API. Per-transaction governor usage is not represented by these readings."><div className="grid gap-3 md:grid-cols-2">{entries.map(([name, metric]) => <Usage key={name} title={name.replace(/([a-z])([A-Z])/g, '$1 $2')} metric={metric} unit={name.endsWith('MB') ? 'MB' : ''} />)}</div>{!entries.length && <p className="py-6 text-center text-sm text-slate-500">Limits are unavailable for this Salesforce user or org.</p>}</Card>
  </div>;
}
