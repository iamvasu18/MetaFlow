// Explicit repair requests execute an operation; diagnostic questions remain chat.
export function repairRequest(text) {
  return /^(?:(?:can|could|will) you\s+)?(?:please\s+)?(?:fix|resolve|repair|correct)(?:\s+(?:it|this|that|the\s+(?:error|issue|problem|plan|code)|errors?))?[?!. ]*$/i.test(text.trim());
}
export function repairTarget(bundle, failures) {
  const targets = (bundle?.components || []).filter(component => failures(component).length);
  if (targets.length === 1) return targets[0];
  if ((bundle?.components || []).length === 1) return bundle.components[0];
  return null;
}
