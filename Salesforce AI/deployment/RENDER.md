# MetaFlow on Render: installation and operation

This update packages the existing approved-source workflow. It does not perform
Salesforce deployments, copy your local database, or create paid cloud resources.
The Render Blueprint provisions paid web/worker/Postgres/Key Value services in
Singapore. Review the displayed charges before applying it. This is a demo
hosting baseline, not a completed production security/backup/rollback program.

## File locations
Merge the update ZIP into Desktop/AI (repository root). render.yaml and
.github/workflows/ci.yml belong there. The remaining files belong inside
Salesforce AI. Existing main.py and job_worker.py are preserved: the container
uses deployment/start.py to wrap their startup.

## Verify before cloud provisioning
1. Stay on stage2-hosting-cd. Copy the files, inspect git diff, then build locally:
   cd "Salesforce AI"
   docker build -t metaflow-render .
   Docker Desktop must be running. No local .env or application data is copied.
2. Commit this update and push a PR. Wait for all CI jobs, including Render
   container build, to pass. Merge, then pull main locally. Never deploy a build
   whose image check failed. The startup unit tests are isolated; the container
   CI checks Python/Node/LWC compiler presence and frontend output.

## Shared credentials before creating the Blueprint
In Render create an Environment Group named metaflow-shared. Add these values
manually in its dashboard (never in Git or chat):
- APP_ENCRYPTION_KEY: valid Fernet key. Use the EXISTING key if importing the
  existing database; a different key cannot decrypt those tokens. For a brand-new
  cloud database you may use a new Fernet key. Both services MUST share it.
- Server SF_OAUTH_CLIENT_ID/SF_OAUTH_CLIENT_SECRET are optional legacy defaults.
  New connections enter their own OAuth app credentials in Settings > Salesforce.
- ANTHROPIC_API_KEY/ANTHROPIC_MODEL are optional server defaults. Users configure
  their own Anthropic key/model through Settings > AI provider.
The Blueprint creates/updates the same group with nonsecret flags. Omitted
existing keys are preserved. Do not use generateValue separately per service.

## Provision the application
Choose New > Blueprint, select MetaFlow, main, and root render.yaml. Review the
four resources, region and charges before applying. The Blueprint references
private Postgres/Key Value connections; it does not expose their external ports.
APP_PUBLIC_URL is derived from metaflow-web's RENDER_EXTERNAL_URL for both web
and worker; callback is computed as that origin + /api/orgs/callback. A custom
APP_PUBLIC_URL/SF_OAUTH_CALLBACK_URL must be configured consistently on both
services if you later use a custom domain.

Register the EXACT new HTTPS callback URL in your Salesforce OAuth app before
connecting any org. Keep the existing localhost callback if you still use it.
No Salesforce username/password is entered into the Render environment.

The cloud database starts EMPTY. Sign up/log in and connect a demo org there.
Your local Docker Postgres data remains local; this update does not migrate it.
If you require existing chats/accounts, stop and plan a PG backup/restore with
the original encryption key. Do not restore into a database containing new data.

## Checks after deployment
- /health: application liveness; /ready: Postgres read succeeds. Readiness does
  NOT certify Salesforce, AI, Redis or the worker. Redis outages retain the
  existing timed Postgres scans.
- Open /login and /workspace directly; page refresh should work.
- Verify signup/login, OAuth connect, chat generation, approval/check-only
  validation, and explicit deployment to a demo org. Verify the real component
  in Salesforce. No paid resource, live login, or deployment was tested by the
  generated update's local tests.
- Confirm worker structured startup/job events and request IDs in web logs.
- Restart the worker during a queued task and verify existing recovery behavior.
- Local development still uses the original Uvicorn and npm commands.

## CI/CD and Docker responsibilities
GitHub CI runs regression/replay, frontend tests/audits/build and a container
build. Render autoDeployTrigger checksPass deploys commits to main after checks
pass. Initial Blueprint creation and manual deploys are separate actions; inspect
CI before using them. Render independently builds web and worker images from
that commit; updates are NOT an atomic multi-service release.

Docker packages Python, Node, the LWC checker and compiled React. It does not
run your local Docker databases in Render. Render manages separate Postgres and
Redis-compatible Key Value resources. Saved workspace packages contain source
in Postgres; local temporary staging is recreated for API operations, so there
is no shared disk. Legacy local file-only endpoints/CLI paths are not promoted
to durable hosted workflows. No Salesforce CLI is installed in this image.

The container runs one nonroot web process and one independent worker service.
Do not increase workers/instances before concurrency/load and migration tests.
Graceful SIGTERM handling exists in the worker, but in-flight external requests
and ambiguous Salesforce outcomes still require recovery/status verification.

## Limits and rollback
New dependency installs are governed by existing requirements.txt (Python is not
yet fully locked). Image build/runtime checks must pass in CI. An actual Docker
build was not available in the assistant's environment; verify locally/CI.

Render's code rollback is not a database rollback or Salesforce rollback. Keep
managed database backups and review schema compatibility before rollback.
Role-based approvals, production promotion, Salesforce predeploy backup and
rollback, security review and error-tracking integrations remain future work.
The existing application allows account registration; restrict audience/use
before exposing customer or production orgs. Keep credentials out of logs.


## User-owned Salesforce OAuth applications
New connections use Settings > Salesforce: environment, exact My Domain URL,
Salesforce username, Consumer Key and Consumer Secret. The UI displays the exact
callback URL to register in each user's OAuth app. API + refresh_token scopes
and Authorization Code / PKCE support are required. Users then log in and grant
access on Salesforce itself; no Salesforce password/security token is collected.
Only Salesforce My Domain HTTPS hosts are accepted. The authenticated username
and returned instance must match the submitted identity; mismatches are rejected.
Secrets are encrypted in pending OAuth state (10 minute expiration) and then in
that connection's token payload. Existing server-app connections retain their
old refresh behavior; new custom-app refresh/reconnect uses its saved credentials.
Removing an app connection removes its tokens; it does not revoke Salesforce's
OAuth grant. Secret rotation requires reconnecting with new credentials. Supply
new credentials by using the connection form when the old app secret is revoked.
The provider UI supports Anthropic Claude, OpenAI Responses-compatible text
models, and Gemini Developer API generateContent-compatible text models. Azure
OpenAI, Vertex AI, arbitrary gateways and non-text models are not supported.
Select a provider, enter its own key/model, then Save & verify. OpenAI/Gemini
verification makes a small billable text request. Keys are account-scoped and
encrypted; changing providers never reuses another provider's saved key.
OpenAI/Gemini use fixed HTTPS endpoints, real input-token counts, bounded
timeouts, no automatic network retries and reject incomplete output.
Set AI_MAX_INPUT_TOKENS/AI_MAX_OUTPUT_TOKENS on the server if needed; actual
model limits still apply. Optional server defaults use OPENAI_API_KEY/OPENAI_MODEL
or GEMINI_API_KEY/GEMINI_MODEL with AI_PROVIDER matching that provider.
Live provider billing, access and model output quality require smoke tests.
