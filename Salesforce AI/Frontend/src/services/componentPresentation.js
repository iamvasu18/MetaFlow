const list = value => Array.isArray(value) ? value : value && typeof value === 'object' ? [value] : [];

export function salesforceDetails(bundle) {
  const report = bundle?.lastResult;
  return (report?.result || report)?.details || {};
}

function plain(value) {
  return String(value || '').replace(/<[^>]*>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

function matches(failure, component) {
  const path = String(failure.fileName || failure.filePath || '').replaceAll('\\', '/');
  const name = component.fullName;
  const [object, member] = name.split('.');
  if (failure.fullName === name || failure.fullName === `markup://c:${name}`) return true;
  if (component.metadataType === 'ApexClass') return path.endsWith(`classes/${name}.cls`) || path.endsWith(`classes/${name}.cls-meta.xml`);
  if (component.metadataType === 'ApexTrigger') return path.endsWith(`triggers/${name}.trigger`);
  if (component.metadataType === 'LightningComponentBundle') return path.includes(`lwc/${name}/`) || path.endsWith(`lwc/${name}`);
  if (component.metadataType === 'PermissionSet') return path.endsWith(`permissionsets/${name}.permissionset`) || path.endsWith(`permissionsets/${name}.permissionset-meta.xml`);
  if (component.metadataType === 'Flow') return path.endsWith(`flows/${name}.flow`) || path.endsWith(`flows/${name}.flow-meta.xml`);
  if (component.metadataType === 'CustomObject') return path.endsWith(`objects/${name}.object`) || path.endsWith(`objects/${name}/${name}.object-meta.xml`);
  if (['CustomField', 'ValidationRule'].includes(component.metadataType)) {
    return path.endsWith(`objects/${object}.object`) || (path.includes(`objects/${object}/`) && path.includes(`/${member}.`));
  }
  return false;
}

export function componentErrors(bundle, component) {
  const item = bundle?.plan?.items?.find(item => item.metadataType === component.metadataType && item.fullName === component.fullName);
  const errors = list(item?.validation?.errors).map(error => plain(typeof error === 'string' ? error : error.message));
  const details = salesforceDetails(bundle);
  for (const failure of list(details.componentFailures)) {
    if (!matches(failure, component)) continue;
    const line = failure.lineNumber ?? failure.line;
    const column = failure.columnNumber ?? failure.column;
    const location = line ? `Line ${line}${column ? `, column ${column}` : ''}: ` : '';
    errors.push(location + plain(failure.problem || failure.error || failure.message));
  }
  for (const failure of list(details.runTestResult?.failures)) {
    const testName = failure.name || failure.className;
    if (component.metadataType !== 'ApexClass' || testName !== component.fullName) continue;
    errors.push(`Test ${failure.methodName || testName}: ${plain(failure.message)}${failure.stackTrace ? `\n${plain(failure.stackTrace)}` : ''}`);
  }
  for (const warning of list(details.runTestResult?.codeCoverageWarnings)) {
    if (warning.name === component.fullName) errors.push(`Coverage: ${plain(warning.message)}`);
  }
  return [...new Set(errors.filter(Boolean))];
}

export function packageErrors(bundle) {
  const details = salesforceDetails(bundle);
  const components = bundle?.components || [];
  return list(details.componentFailures)
    .filter(failure => !components.some(component => matches(failure, component)))
    .map(failure => `${failure.fullName || failure.fileName || 'Package'}: ${plain(failure.problem || failure.message)}`);
}

export function relatedCoverageNotes(bundle, component) {
  if (component.metadataType !== 'ApexClass' || !bundle?.testClasses?.includes(component.fullName)) return [];
  return list(salesforceDetails(bundle).runTestResult?.codeCoverageWarnings)
    .map(warning => `Package coverage: tests need to cover ${warning.name || 'the production class'}. ${plain(warning.message)} Use Fix with AI on the production class to repair it and its tests together.`);
}
