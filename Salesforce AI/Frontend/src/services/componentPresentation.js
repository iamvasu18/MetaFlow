export function componentErrors(bundle, component) {
  const item = bundle.plan?.items?.find(item => item.metadataType === component.metadataType && item.fullName === component.fullName);
  const errors = (item?.validation?.errors || []).map(error => typeof error === 'string' ? error : error.message || JSON.stringify(error));
  const failures = bundle.lastResult?.result?.details?.componentFailures || [];
  for (const failure of failures) {
    const path = String(failure.fileName || '').replaceAll('\\', '/');
    const name = component.fullName;
    const [object, field] = name.split('.');
    const matches = failure.fullName === name || failure.fullName === `markup://c:${name}` ||
      (component.metadataType === 'LightningComponentBundle' && path.includes(`lwc/${name}/`)) ||
      (component.metadataType === 'CustomField' && (path.includes(`/fields/${field}.`) || path === `objects/${object}.object`)) ||
      (component.metadataType === 'CustomObject' && path === `objects/${name}.object`);
    if (matches && failure.problem) errors.push(failure.problem);
  }
  return [...new Set(errors)];
}
