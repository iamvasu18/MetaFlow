# Cumulative release candidate

Extract into Desktop\AI preserving the paths. This replaces the earlier update ZIPs. Restart backend, worker and frontend. No .env, databases, org exports, host-port Compose settings, dependency folders or Git history are included.

## Implemented

Catalog-based completed field-parent replies, concise blockers, explicit create/update Flow timing, combobox typing, bounded Flow typing correction, structured Flow repair, preservation checks for existing operation targets/field assignments/decision conditions/input contracts, natural-language repair/retry routing and exact-source invalidation are included.

Shared task-specific Flow/Apex/LWC/integration rules are applied across planning, generation and repair. Existing backend local checks and Salesforce check-only/approval/deployment gates remain. Mandatory source checks include user-mode access, sharing, bulk-loop restrictions, async companion entry-point tests, verified LWC Apex imports/parameters/cacheability, imperative rejection handlers and supported serialization contracts.

LWC generation now requests Jest tests. Supplied tests are syntax checked and cannot contain skip/only/todo or constant assertions. They are stored separately as verificationFiles and exported in the source ZIP under verification/behavior-tests.json; they are not deployed metadata. States are pending/missing/stale, never passed simply because AI generated tests. Source edits invalidate previous behavioral evidence. Use an approved Salesforce DX Jest toolchain in a reviewed test environment to execute these tests. Generated tests remain subject to review and do not prove all behavior automatically.

HTTP callouts have a deliberately narrow contract: the requirement names an existing Named Credential, owned Metadata API discovery verifies its exact identity, endpoint is literal callout:Name/path, timeout is bounded, Queueable/Batch classes implement AllowsCallouts, sends inside record loops are rejected, and HttpCalloutMock/Test.setMock tests are required. Raw/dynamic endpoints and email sending remain unsupported. Verify External Credential principal access and integration behavior in a sandbox; source validation alone does not establish runtime access. New Named Credentials are not created or granted by this update.

## Verification

403 selected backend CI tests passed, followed by 10 callout tests (including two added cases). 38 frontend tests and production build passed. Replay evaluations: 15/15. Suites overlap; do not sum counts. These application tests use mocked Salesforce calls. A separate experimental Jest runner executed three loading/error/empty fixture tests successfully, but its dependency audit reported 31 high issues; that runner and dependencies are excluded from this release and the hosted Docker image.

## Remaining acceptance blockers

This is not unrestricted production certification. Live Salesforce compilation, actual tests/coverage, integration permission checks, browser behavior and sandbox end-to-end acceptance have not been performed here. Nine legacy HTTP tests still need migration to the authenticated unified workflow. Existing external-controller reuse, arbitrary dynamic queries, email sending, all Flow Orchestration/Data Cloud features and a complete governor-limit/security proof are not implemented. Generated Jest execution is not an automatic trusted deployment gate. Do not claim every Salesforce requirement is supported.

## Local test sequence

Verify login/history, generate a fresh simple field with a parent answer, generate the Case escalation Flow and inspect preserved conditions/actions, generate an Apex-backed LWC with controller/tests, and use Fix with AI against actual errors. Approval and deployment require the exact validated source. Existing rejected or saved source is not automatically rewritten by copying application files. Rebuild/check Docker from Salesforce AI before pushing a new branch; merge only after CI passes.
