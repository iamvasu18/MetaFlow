import { useOutletContext } from 'react-router-dom';
import { Activity } from 'lucide-react';
import StatCard from './StatCard';
import Card from '../ui/Card';

// eslint-disable-next-line react-refresh/only-export-components
export function useIntelligence() { return useOutletContext(); }
// eslint-disable-next-line react-refresh/only-export-components
export function amount(value) { return typeof value === 'number' ? value.toLocaleString() : '—'; }
export function MetricGrid({ items }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">{items.map(({ label, value, detail, icon }) => <StatCard key={label} title={label} value={typeof value === 'number' ? amount(value) : value ?? '—'} subtitle={detail || 'Unavailable values are shown as —'} icon={icon || Activity} />)}</div>;
}
export function Usage({ title, metric, unit = '' }) {
  const percentage = metric?.percentage;
  return <div className="rounded-xl border border-slate-200 p-4 dark:border-zinc-800"><div className="flex items-center justify-between gap-3"><h3 className="text-xs font-semibold">{title}</h3><span className="text-xs text-slate-500">{percentage == null ? 'Unavailable' : `${percentage}% used`}</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-zinc-800">{percentage != null && <div style={{ width: `${Math.max(0, Math.min(100, percentage))}%` }} className={`h-full rounded-full ${percentage >= 90 ? 'bg-red-500' : percentage >= 75 ? 'bg-amber-500' : 'bg-emerald-500'}`} />}</div><p className="mt-2 text-xs text-slate-500">{metric ? `${amount(metric.used)} / ${amount(metric.limit)} ${unit} · ${amount(metric.remaining)} remaining` : 'Not returned by Salesforce for this user or org.'}</p></div>;
}
export function InventoryTable({ title, description, headers, rows }) {
  return <Card title={title} description={description}><div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{headers.map(header => <th className="border-b border-slate-200 px-3 py-3 font-semibold text-slate-500 dark:border-zinc-800" key={header}>{header}</th>)}</tr></thead><tbody>{rows?.map((row, index) => <tr className="border-b border-slate-100 last:border-0 dark:border-zinc-800" key={index}>{row.map((cell, i) => <td className="px-3 py-3" key={i}>{cell ?? '—'}</td>)}</tr>)}</tbody></table>{!rows?.length && <p className="p-5 text-sm text-slate-500">{rows == null ? 'This inventory is unavailable. See the metric access details above.' : 'No records found in the current Salesforce view.'}</p>}</div></Card>;
}
