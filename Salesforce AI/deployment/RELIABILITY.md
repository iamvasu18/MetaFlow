# Combined generation reliability update

Apply this replacement-file update to the repository root (Desktop\AI), retaining the Salesforce AI subfolder and .github folder paths. Stop the backend and worker before copying, then restart them. The ZIP excludes credentials, databases, org exports and dependencies.

Changes include concise necessary clarifications, independent request context, coordinated Apex and async tests, verified Apex-backed LWC alongside LDS/UI API, picklist formula checks, exact component error attribution, automatic failed-operation reports, stale response guards and bounded AI requests with timing diagnostics.

Generate creates files and runs local checks followed by Salesforce check-only validation. Approve applies to the exact validated source. Deploy applies that source to Salesforce. Editing or AI repair invalidates approval and validation. Existing failed drafts need a repair or regeneration; replacing application files does not automatically rewrite saved source.

Apex checks reject invalid Assert methods, bare SOQL NOW(), direct Exception construction, unsafe direct DML and certain async/bulk mistakes. These source checks do not prove every Salesforce rule or governor limit. Salesforce must compile the actual package and run its tests and required coverage. Deploying an async class does not enqueue or schedule it.

Apex-backed LWC supports declared same-package controllers and companion tests. External controller reuse, arbitrary callouts and dynamic SOQL remain outside the current checked generation contract.

## Windows CMD verification

Run Docker commands inside Salesforce AI:

```bat
cd "Salesforce AI"
docker build -t metaflow-render .
docker run --rm --entrypoint python -e PYTHONPATH=/app metaflow-render deployment/check_image.py
```

Run Git commands at repository root. Create a new branch, stage only the files listed in UPDATE-FILES.txt, inspect the diff, commit and push. Merge after CI passes, then confirm Render deploys that merge commit. This update has not been pushed or deployed for you.

## Verified in the coding workspace

379 configured backend tests passed; 36 frontend tests passed; frontend production build passed; 15/15 replay evaluations passed. External Salesforce and AI calls were mocked in these checks. Docker packaging must be checked on your machine.
