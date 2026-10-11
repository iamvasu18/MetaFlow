import { Layers, Database, Zap, Code2, FileCheck2, GitBranch } from 'lucide-react';
import { MetricGrid, InventoryTable, useIntelligence } from '../../components/dashboard/LiveMetrics';

export default function Metadata() {
  const { data } = useIntelligence();
  const m = data.metrics;
  return <div className="space-y-4"><MetricGrid items={[
    { label: 'Custom objects', value: m.customObjects?.length, detail: 'API-visible custom objects and custom settings', icon: Layers },
    { label: 'Custom fields', value: m.customFields, detail: 'Accessible Tooling API custom fields', icon: Database },
    { label: 'Active flow definitions', value: m.activeFlows, detail: 'Has an ActiveVersionId', icon: Zap },
    { label: 'Inactive flow definitions', value: m.inactiveFlows, detail: 'No ActiveVersionId; not a count of draft versions', icon: GitBranch },
    { label: 'Apex classes', value: m.apexClasses, detail: 'Accessible Tooling API class inventory', icon: Code2 },
    { label: 'Validation rules', value: m.validationRules, detail: 'Includes active and inactive rules', icon: FileCheck2 },
  ]} /><InventoryTable title="Custom object inventory" description="Objects visible through the connected user’s Salesforce API access. Managed custom objects and custom settings can be included." headers={['Label', 'API name']} rows={m.customObjects?.map(object => [object.label, object.name])} />
  </div>;
}
