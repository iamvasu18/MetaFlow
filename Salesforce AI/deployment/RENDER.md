# MetaFlow free demo on Render

## What changed
The root render.yaml now explicitly selects free for the web service, Postgres
and Key Value. There is NO paid background-worker service. deployment/demo.py
supervises the existing web and worker commands as two child processes inside
one web-service container. If either exits, it stops the other and exits so the
whole instance can be restarted. SIGTERM stops both children. Existing durable
Postgres jobs, source approval and explicit Salesforce deployment remain intact.
This is a low-volume demo, not an always-on production deployment.

## Costs and limitations
Only apply a review showing Free / $0 for all three resources and $0 additional
monthly compute charges. Never apply the older $34.50 Blueprint. Free compute
has usage limits; remain on a free workspace and do not enable paid services or
upgrade billing just to bypass a quota. Check Render's dashboard usage limits.
Free web instances sleep after 15 minutes without incoming traffic and may take
about a minute to wake. Web AND worker pause when sleeping. Browser polling
while a demo job is active usually supplies inbound traffic; no guarantee of
uninterrupted background execution after browsers close. PostgreSQL persists
saved packages/jobs across instance restarts, subject to the DB lifetime.
Free Postgres expires 30 days after creation (1GB limit; one per workspace).
Export any demo data you need BEFORE expiry. Free Key Value is not persistent;
notifications can disappear on restart. Jobs remain in Postgres and existing
worker timed scans are the fallback. Do not depend on Redis for durable data.
The 512MB web instance shares memory between Python web/worker and LWC checks.
Limit simultaneous requests and large org contexts; load/memory tests are not
complete. Cold starts and free-tier CPU can slow the demo.

Hosting free instances do NOT make arbitrary LLM APIs free. For a zero-cost AI
demo, use an eligible Gemini Developer API free-tier project/model, confirm its
free-tier quota in Google AI Studio, and do not enable paid billing. Use only
supported text generateContent models. OpenAI/Claude remain available but may
incur provider charges. MetaFlow cannot determine a key's billing tier from its
text or prevent charges on a paid provider account. Save & verify makes a small
model request. Check the provider's terms and use demo org metadata.

## Install and verify
Merge this update into Desktop/AI (repo root), preserving folders.
Create a new feature branch, review changes, and run from Salesforce AI:
  docker build -t metaflow-render .
  docker run --rm --entrypoint python -e PYTHONPATH=/app metaflow-render deployment/check_image.py
  docker run --rm --entrypoint python -e PYTHONPATH=/app -e APP_DATABASE_URL= -e APP_DATABASE=/tmp/demo-tests.sqlite3 -e APP_JOB_MODE=embedded -e APP_BACKGROUND_JOBS=false metaflow-render -m pytest Backend/AI/app/tests/test_demo_hosting.py Backend/AI/app/tests/test_hosting.py -q
Commit, push a PR, wait for backend/frontend/container CI, merge and pull main.
The generated update's supervisor tests use fake processes; live Render startup
and memory behavior still require verification. No cloud resources were created.

## Render setup
Cancel/back out of the unsubmitted paid Blueprint review. Preserve the existing
metaflow-shared Environment Group and its APP_ENCRYPTION_KEY. Don't regenerate
this key. After the free update is merged, reload the Blueprint from main with
root render.yaml. Expect exactly metaflow-web, metaflow-db and
metaflow-notifications. Keep Associate existing services so the encryption group
is retained. No metaflow-worker service should be created. Review the $0 plans
before applying. If resources were already created with paid plans, stop and
check billing/resources before changing/deleting them; a YAML update alone is
not evidence that paid resources stopped billing.

The Blueprint adds shared secure-cookie/job flags and defaults AI_PROVIDER to
gemini. No server Salesforce or AI key is required. Private database connection
strings are injected automatically. APP_PUBLIC_URL follows the web service's
Render HTTPS URL, and start.py derives the callback /api/orgs/callback.
The cloud database starts empty; local Docker Postgres is not migrated or changed.

## Live smoke test
Wait for metaflow-web to be live. /health checks liveness and /ready checks
Postgres; supervisor termination reacts if web or worker exits. /ready does not
prove AI, Salesforce or Redis access. Inspect web and worker startup logs.
Open /login or /workspace directly, sign up, then Settings:
- Salesforce: choose environment, My Domain URL, username, Consumer Key/Secret.
  Register the exact callback shown in your Salesforce External Client App.
  Enable Authorization Code/PKCE and api/refresh_token scopes. Log in/authorize
  on Salesforce. Tokens and custom OAuth credentials are encrypted per org.
- AI provider: choose Gemini, enter a free-tier key and supported model, Save &
  verify. Secrets are encrypted per account and not returned to the browser.
Generate one small plan, review source, approve for validation and explicitly
confirm deployment to a demo org. Check the created component in Salesforce.
Test a restart and idle wake separately; free hosting is not production-ready.

## CI/CD and later transition
GitHub runs tests, evaluations, frontend audits/build and image build checks.
Render autoDeployTrigger checksPass deploys main after CI passes. Initial
Blueprint creation/manual deploys still need review. Local Docker builds package
software; Render runs that packaging on its infrastructure, not your laptop's
Postgres/Redis containers. Nothing automatically deploys Salesforce metadata.

After demo acceptance, plan paid independent workers, backups, scaling/security,
error tracking and production controls. Code rollback does not roll back the
Postgres schema or Salesforce changes. Keep the encryption key safe and stable.
References: https://render.com/docs/free ; https://render.com/docs/blueprint-spec ;
https://ai.google.dev/gemini-api/docs/pricing
