// Display grants from the exact saved XML, including source edits, rather than stale plan config.
export function permissionGrantSummary(bundle, name) {
  const source = bundle?.files?.[`force-app/main/default/permissionsets/${name}.permissionset-meta.xml`];
  if (!source || typeof DOMParser !== 'function') return ['Open Edit to review the saved permission XML.'];
  const document = new DOMParser().parseFromString(source, 'application/xml');
  if (document.getElementsByTagName('parsererror').length) return ['Permission XML is invalid. Review and repair it before approval.'];
  const ns = 'http://soap.sforce.com/2006/04/metadata';
  const text = (entry, key) => entry.getElementsByTagNameNS(ns, key)[0]?.textContent || '';
  const entries = key => Array.from(document.getElementsByTagNameNS(ns, key));
  const grants = [];
  for (const entry of entries('objectPermissions')) {
    const flags = [['allowRead', 'Read'], ['allowCreate', 'Create'], ['allowEdit', 'Edit'], ['allowDelete', 'Delete'], ['viewAllRecords', 'View All'], ['modifyAllRecords', 'Modify All']].filter(([key]) => text(entry, key) === 'true').map(([, label]) => label);
    if (flags.length) grants.push(`${text(entry, 'object')}: ${flags.join(', ')}`);
  }
  for (const entry of entries('fieldPermissions')) {
    const flags = ['readable', 'editable'].filter(key => text(entry, key) === 'true');
    if (flags.length) grants.push(`${text(entry, 'field')}: ${flags.join(', ')}`);
  }
  for (const entry of entries('classAccesses')) if (text(entry, 'enabled') === 'true') grants.push(`Apex access: ${text(entry, 'apexClass')}`);
  for (const entry of entries('userPermissions')) if (text(entry, 'enabled') === 'true') grants.push(`System permission: ${text(entry, 'name')}`);
  return grants.length ? grants : ['No enabled access grants are present.'];
}
