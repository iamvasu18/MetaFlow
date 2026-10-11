export const BLOCKED_STATES = new Set([
  "queued",
  "running",
  "pending",
  "unknown",
  "deployed",
  "rejected",
]);

export function canValidate(bundle) {
  return Boolean(
    bundle?.id && !BLOCKED_STATES.has(bundle.state)
  );
}

export function canDeploy(bundle, approvedHash) {
  if (
    !bundle?.sourceHash ||
    approvedHash !== bundle.sourceHash
  ) {
    return false;
  }

  // Approval and successful Salesforce validation must cover the same files.
  if (bundle.plan) {
    return (
      bundle.approvedHash === bundle.sourceHash &&
      bundle.validatedHash === bundle.sourceHash &&
      bundle.state === "validated"
    );
  }

  // Preserve standalone Apex/LWC workflow compatibility.
  return bundle.state === "validated";
}

export function buildRequest(
  kind,
  { name, requirement, org, objects, targets }
) {
  const common = {
    requirement: requirement.trim(),
    target_org: org.trim(),
    objects: objects
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean),
  };

  return kind === "apex"
    ? {
        ...common,
        class_name: name.trim(),
      }
    : {
        ...common,
        component_name: name.trim(),
        targets,
      };
}

export function statusText(bundle) {
  const labels = {
    rejected: "Plan rejected. No changes were deployed.",
    generated: "Implementation package ready for review",
    validated:
      "Salesforce validation passed. No metadata was deployed.",
    deployed:
      "Deployment completed successfully in Salesforce",
    queued:
      "The approved operation is queued for the worker. No Salesforce submission has been confirmed yet.",
    pending:
      "Salesforce is processing the saved job. Status updates automatically.",
    running:
      "An operation is running. Refresh the saved package before taking another action.",
    unknown:
      bundle?.operation === "validate"
        ? "Validation could not be confirmed. Check the job status before continuing."
        : "Deployment outcome could not be confirmed. Check Salesforce Deployment Status before retrying.",
    failed:
      "Salesforce operation failed. Review the results below.",
  };

  return labels[bundle?.state] || "Ready";
}

export function statusLabel(bundle) {
  if (bundle?.state === "unknown") {
    return bundle.operation === "validate"
      ? "Validation not confirmed"
      : "Deployment not confirmed";
  }

  const labels = {
    rejected: "Rejected",
    generated: bundle?.localChecks?.valid ? "Local checks passed" : "Ready for review",
    validated: "Salesforce validated",
    deployed: "Deployed",
    queued: "Queued",
    pending: "In progress",
    running: "Processing",
    failed: "Needs attention",
  };

  return labels[bundle?.state] || "Ready";
}

export function isStandaloneRequirement(message) {
  const text = message.trim();
  if (!/^(?:please\s+)?(?:create|build|generate)\b[\s\S]*\b(?:named|called)\s+\S/i.test(text)) return false;
  if (!/\b(?:object|field|flow|class|trigger|lwc|lightning web component|validation rule)\b/i.test(text)) return false;
  // Field/validation requests need their own parent. A rename answer without
  // a parent keeps the pending clarification's context.
  if (/\b(?:field|validation rule|trigger)\b/i.test(text)) {
    return /\b(?:on|for)\s+(?:the\s+)?[A-Za-z][A-Za-z0-9_]*/i.test(text);
  }
  return true;
}

export function conversationRequirement(previous, message, clarification, bundle, { continuing = false, referenceOnly = false } = {}) {
  const text = message.trim();
  if (!text) throw new Error('Enter a message.');
  let result;
  if (isStandaloneRequirement(text)) {
    result = text;
  } else if (clarification) {
    result = `${previous}\n\nClarification question: ${clarification.question}\nUser answer: ${text}`;
  } else if (bundle?.state === 'deployed') {
    result = `Previous deployed implementation (context only; do not recreate):\n${bundle.requirement}\n\nImplement only this follow-up change, using the connected org:\n${text}`;
  } else if (bundle) {
    result = `${bundle.requirement}\n\nFollow-up instruction for a new reviewable draft:\n${text}\nPreserve the earlier requested behavior unless this instruction explicitly changes it.`;
  } else if (continuing && previous) {
    result = referenceOnly
      ? `Earlier conversation context (reference only; do not recreate):\n${previous}\n\nImplement only this follow-up change, using the connected org:\n${text}`
      : `${previous}\n\nFollow-up instruction for a new reviewable draft:\n${text}`;
  } else {
    result = text;
  }
  if (result.length > 40000) throw new Error('The accumulated requirement is too long. Submit a concise combined requirement.');
  return result;
}
