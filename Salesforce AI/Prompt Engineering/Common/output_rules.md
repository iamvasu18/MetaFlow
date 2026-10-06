# Salesforce AI Output Rules

Rule Set: salesforce_output
Version: v001
Status: active

## PURPOSE

These rules define how Salesforce AI tasks must format and return
their output.

The objective is to ensure that AI responses are deterministic,
machine-readable, schema-compatible, and safe for application
processing.

---

## GENERAL OUTPUT RULES

1. Follow the output format defined by the active task.

2. When the task requires JSON, return only valid JSON.

3. Do not include conversational text before or after structured output.

4. Do not include Markdown code fences around JSON.

5. Do not include comments inside JSON.

6. Do not include explanatory notes outside the required structure.

7. Do not invent additional top-level properties unless the active
   schema explicitly permits them.

8. Use property names exactly as defined by the active schema.

---

## JSON OUTPUT

When JSON output is required, the response must be directly parseable
by a standard JSON parser.

Correct:

{
  "id": "PLAN-001",
  "status": "DRAFT"
}

Incorrect:

Here is the implementation plan:

{
  "id": "PLAN-001",
  "status": "DRAFT"
}

Incorrect:

```json
{
  "id": "PLAN-001",
  "status": "DRAFT"
}