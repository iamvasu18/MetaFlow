import { Users, KeyRound, ShieldCheck } from 'lucide-react';
import { MetricGrid, InventoryTable, amount, useIntelligence } from '../../components/dashboard/LiveMetrics';

export default function LicensesUsers() {
  const { data } = useIntelligence();
  const m = data.metrics;
  const licenses = m.licenses;
  const adoption = m.enabledUsers > 0 && m.recentUsers != null ? Math.round(m.recentUsers / m.enabledUsers * 100) : null;
  return <div className="space-y-4"><MetricGrid items={[
    { label: 'Total users', value: m.totalUsers, detail: 'All User records, including inactive users', icon: Users },
    { label: 'Enabled users', value: m.enabledUsers, detail: 'Active Salesforce user accounts', icon: Users },
    { label: 'Recently logged in', value: m.recentUsers, detail: 'Enabled users with a login in the last 30 days', icon: Users },
    { label: 'Login adoption', value: adoption == null ? '—' : `${adoption}%`, detail: 'Recent logins / enabled users', icon: Users },
    { label: 'Never logged in', value: m.neverLoggedIn, detail: 'Enabled users with no recorded login', icon: Users },
    { label: 'Frozen users', value: m.frozenUsers, detail: 'Frozen UserLogin records', icon: ShieldCheck },
    { label: 'Profiles', value: m.profiles, detail: 'Accessible profile inventory', icon: KeyRound },
    { label: 'Permission sets', value: m.permissionSets, detail: 'Excludes permission sets owned by profiles', icon: KeyRound },
  ]} /><InventoryTable title="License allocation" description="Salesforce UserLicense records. Unlimited or unavailable allocations are not combined into a misleading total." headers={['License', 'Total', 'Assigned', 'Available']} rows={licenses?.map(license => [license.Name, license.TotalLicenses < 0 ? 'Unlimited' : amount(license.TotalLicenses), amount(license.UsedLicenses), typeof license.TotalLicenses === 'number' && license.TotalLicenses >= 0 && typeof license.UsedLicenses === 'number' ? amount(Math.max(0, license.TotalLicenses - license.UsedLicenses)) : '—'])} />
    <MetricGrid items={[
      { label: 'Login attempts', value: m.recentLogins, detail: 'LoginHistory entries in the last 30 days' },
      { label: 'Failed login attempts', value: m.failedLogins, detail: 'Last 30 days, Status differs from Success' },
    ]} />
  </div>;
}
