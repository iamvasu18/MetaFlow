# Stage 1 evaluation and trust update

This update hardens the current **single-process** app. It does not migrate the
app to REST/Metadata API transport, a queue, Postgres or Redis. It does not claim
live Salesforce validation success from replay fixtures.

## Installation

Stop the backend. Copy the ZIP's `Backend` and `evaluations` folders into the
Salesforce AI project root, replacing matching files and keeping other files.
Do not overwrite your `.env`. No new Python dependency is required.
Restart from the project root:

```cmd
python -m uvicorn Backend.AI.app.main:app --reload --env-file .env
```

The SQLite additions use `CREATE TABLE IF NOT EXISTS`; existing accounts,
connections, plans and chats remain. Evaluation begins with new activity after
installation; historical results are not invented. No frontend changes are
included or required.

## Safety changes

- Shared portable component-name/path checks run during plan/spec validation,
  before generator writes, and before staging/archive extraction. Both `files`
  and `baseFiles` are checked. Traversal, drive/alternate-stream syntax, Windows
  reserved names, malformed path segments and symlink aliases are rejected.
  Each generator batch preflights all names before writing the first component.
- Existing-object detection also uses described objects when the catalog is
  absent. Explicit standard-object collisions remain clarifications.
- The job monitor takes a nonblocking per-plan lock. It skips an active
  submission and recovers an interrupted `running` state to `unknown`. Known
  jobs are polled; operations with uncertain outcomes are never resubmitted.
  Already-loaded status reads do not wait behind CLI submission locks.
- Successful real deployment invalidates planning and overview caches even if
  a later application test-report check fails. Cache epochs prevent older
  in-flight reads from refilling invalidated entries. Validation does not
  invalidate metadata because it does not change the org.
- Submission and restore mutations share per-plan locks. Legacy CREATE/UPDATE fallback routes and dry-run execution
  are **disabled by default**. The old implementation remains
  for Stage 4 modernization. `APP_ENABLE_LEGACY_WORKFLOW=true` is an explicit
  opt-in to the old implementation, not a production-readiness setting.
- Structural inspection found no statements after unconditional exits to
  delete. This update quarantines legacy workflow routes rather than deleting
  future UPDATE support on the basis of an unused-call count.

These locks coordinate one process only. Do not run multiple Uvicorn workers
until Stage 2 adds shared job ownership and transactional leases. File checks
assume the server controls its source directories; they do not protect against
another privileged process replacing paths between checks and writes.

## Repeatable evaluation

From the project root:

```cmd
python -m evaluations.run --mode replay --output evaluation-results.json
```

The versioned corpus has 15 scenarios: existing object/field/Flow/Apex/LWC/rule
conflicts, new components, reporting, picklist defaults, independent date math,
and invalid names/Flow graphs/formula references. Replay checks the golden
responses and rejection guards. It is **not** a measurement of model quality.

To evaluate a changed prompt/model against the same synthetic org snapshot:

```cmd
python -m evaluations.run --mode model --output model-evaluation-results.json
```

The explicit model mode calls the configured Anthropic model and can incur API
cost. It never connects to Salesforce, approves a plan, validates a deployment
or deploys metadata. Behavior cases use the model; adversarial cases always
replay their fixed invalid response. Reports include corpus/context versions,
model, prompt hashes, case decisions, time and actual token usage where
available. Compare behavior-case results between runs; guard-case passes do
not establish source-compilation or Salesforce correctness.

## Live metrics

While signed into the app, open:

```
http://localhost:5173/api/evaluation/summary
```

Optionally add `?org_id=<connected-app-org-id>`. The endpoint is authenticated
and scoped to your account; it rejects orgs owned by other users.

The persisted immutable events track:

1. **Acceptance without edits:** first approved source equals the original
   review-ready source, divided by all generated plans. Unapproved drafts stay
   in the denominator. Source repairs do not replace the original baseline.
   Selected subsets retain their original generation identity rather than
   inflating generated-plan counts. Requirement revisions are new generations.
2. **First-try validation:** first validation operation per plan with a known
   terminal outcome. Pending/unknown outcomes are shown separately. Repeated
   status polling does not add attempts. This is the app's approved validation
   operation, including its preflight; it is not a whole-org quality score.
3. **Generation cost/time per saved plan:** includes review preparation and associated repairs. Initial
   failed attempts appear in attempt totals, including their time and known
   usage. Validation/deployment wait time is separate (`operationSeconds` in
   the package/status response), and Salesforce-side billing is not measured.

Approval indicates accepted source, not proof of business correctness. Metric
numerators/denominators and cost-coverage counts are returned explicitly so
pending work and missing pricing cannot be hidden by an average.

Cost is `null` unless actual provider usage and all needed model-specific rates
are available. Configure USD-per-million-token rates using `AI_PRICING_JSON` in
`.env`; use the exact model ID returned by your provider and your contracted
rates. This is the structure, **not real pricing**:

```
AI_PRICING_JSON={"YOUR_MODEL_ID":{"input_tokens":1.0,"output_tokens":5.0,"cache_creation_input_tokens":1.25,"cache_read_input_tokens":0.1}}
```

Events contain hashes, identities, timing and token counts; they do not store
API keys, full prompts, requirements or source code. Existing package/chat
storage remains separate. Retention and aggregate reporting at scale belong
to the Postgres/observability work in Stage 2.

## Verification

Security/recovery/metrics tests:

```cmd
python -m pytest Backend/AI/app/tests/test_stage1_trust.py -q
```

The LWC regression suite requires the project's existing Node tooling:

```cmd
npm ci --prefix tools/lwc
python -m pytest Backend/AI/app/tests/test_lwc_enhanced.py -q
```

Model evaluation and live-org tests were not run as part of offline verification.
Next is Stage 2: replace discovery/submission/polling CLI calls with API clients,
then persistent jobs, Postgres, Redis, encrypted token storage and observability.
Stage 3 adds validated-build quick deploy, promotion, backups, permission sets,
coverage/analyzer checks and role-based approval—not bypassed validation.

## Current verification limits

The focused Stage 1/workspace/layout/discovery suite passed 139 tests and 19
subtests. The real Node LWC checker regression suite passed 36 tests. All 15
replay cases passed. No paid model evaluation or live Salesforce deployment
was performed.

Broader exploratory runs still found three older fixture failures:

- `test_flow_self_update.py::test_real_http_self_update_pipeline`: makes an
  unauthenticated legacy HTTP request; the app correctly returns 401.
- `test_flow_resources.py::test_real_http_formula_plan_to_draft_deploy`: same
  obsolete unauthenticated HTTP setup.
- `test_flow_resources.py::test_planning_retrieves_and_preserves_formula_dependencies`:
  expects the earlier full selector projection; current planning context marks
  omitted details explicitly while retaining complete metadata for validators.

These fixtures need migration to the authenticated workspace contract. They
were not fixed by disabling authentication or reverting context protection.
A full-suite pass is not claimed. Treat this package as tested Stage 1
hardening, not production certification.
