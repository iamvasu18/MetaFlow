# Salesforce Common Rules

Rule Set: salesforce_common
Version: v001
Status: active

## PURPOSE

These rules define the common Salesforce behavior that must be followed
by all Salesforce AI tasks, including planning, metadata generation,
change analysis, testing, and error correction.

The supplied Salesforce organization context is the source of truth for
the current state of the target Salesforce organization.

---

## CURRENT STATE RULES

1. Use the supplied Salesforce context when determining whether a
   Salesforce component already exists.

2. Do not assume that an object, field, relationship, validation rule,
   Flow, Apex class, trigger, permission, record type, or other component
   exists unless it is present in the supplied context.

3. Do not invent existing Salesforce metadata.

4. If a required component already exists and already satisfies the
   requirement, do not recreate or unnecessarily modify it.

5. If a component exists but must be changed to satisfy the requirement,
   treat it as an existing component that requires modification.

6. If the supplied context is insufficient to determine the current
   state safely, identify the uncertainty instead of fabricating
   Salesforce information.

---

## STANDARD AND CUSTOM METADATA RULES

1. Distinguish between standard Salesforce components and custom
   Salesforce components.

2. Do not propose creating a Salesforce standard object.

3. Do not propose creating a standard field that already belongs to a
   standard Salesforce object.

4. Custom objects should follow Salesforce custom object conventions.

5. Custom fields should follow Salesforce custom field conventions.

6. Preserve existing standard Salesforce functionality whenever it
   satisfies the requirement.

7. Prefer configuration over custom code when standard Salesforce
   functionality can satisfy the requirement.

---

## CHANGE RULES

When analyzing Salesforce metadata, use the following meanings:

### CREATE

Use CREATE when the required component does not exist in the supplied
Salesforce context and a new component is required.

### UPDATE

Use UPDATE when the component already exists but must be modified to
satisfy the requirement.

### DELETE

Use DELETE only when the requirement explicitly requests removal and the
operation is supported by the application.

### NO_CHANGE

Use NO_CHANGE when the required component already exists and its current
state already satisfies the requirement.

Do not use CREATE when UPDATE or NO_CHANGE is appropriate.

Do not use UPDATE when no modification is required.

Do not use DELETE unless removal is explicitly required.

---

## MINIMUM CHANGE PRINCIPLE

1. Produce the smallest Salesforce change that satisfies the requirement.

2. Do not modify unrelated objects, fields, automation, permissions, or
   code.

3. Reuse existing Salesforce components when appropriate.

4. Avoid creating duplicate metadata.

5. Avoid introducing Apex when declarative Salesforce functionality can
   satisfy the requirement reliably.

6. Do not redesign unrelated parts of the Salesforce organization.

---

## DEPENDENCY RULES

1. Identify dependencies between Salesforce components.

2. A component must not reference another component that does not exist
   in either:
   - the supplied Salesforce context, or
   - the proposed implementation.

3. New components must be ordered so foundational components are
   available before dependent components.

4. Do not create circular dependencies.

5. Existing components from Salesforce context do not need to be
   recreated merely to satisfy a dependency.

Example:

Custom Object
    ↓
Custom Field
    ↓
Validation Rule
    ↓
Flow

---

## SALESFORCE CONTEXT RULES

1. Treat Salesforce context supplied by the application as authoritative
   for the current planning operation.

2. Do not replace supplied context with assumptions based on general
   Salesforce knowledge.

3. General Salesforce knowledge may be used to understand platform
   behavior, but it must not be used to claim that a specific component
   exists in the target organization.

4. Do not infer fields or relationships that are absent from the supplied
   context.

5. When required metadata is missing from the context, explicitly
   identify the missing information when it materially affects the
   requested task.

---

## REQUIREMENT RULES

1. Implement only what is required by the user's stated requirement.

2. Do not silently add unrelated functionality.

3. When the requirement is ambiguous and the ambiguity materially
   affects implementation, record or report the assumption according to
   the task's output format.

4. Prefer explicit information from the requirement over inferred
   behavior.

5. Do not fabricate business requirements.

---

## METADATA SUPPORT RULES

Only propose metadata types supported by the current application
capabilities for the task being performed.

The currently recognized planning metadata types are:

- CustomObject
- CustomField
- ValidationRule
- Flow
- ApexClass
- ApexTrigger
- PermissionSet
- Profile
- RecordType
- CustomTab
- Report
- Dashboard

A metadata type being recognized by planning does not automatically mean
that every downstream generation or deployment operation supports it.

Respect the capability boundaries supplied by the application.

---

## AUTOMATION RULES

1. Prefer Salesforce declarative functionality when it can reliably
   satisfy the requirement.

2. Use Apex only when the requirement cannot reasonably be implemented
   using supported declarative functionality or when Apex is explicitly
   required.

3. Do not create both declarative automation and Apex for the same
   behavior unless there is a clear requirement.

4. Avoid unnecessary automation.

---

## DATA SAFETY RULES

1. Do not modify or delete Salesforce data unless the task explicitly
   concerns data operations and the application permits that operation.

2. Metadata planning must not be treated as authorization to modify
   Salesforce records.

3. Do not include Salesforce credentials, session IDs, access tokens,
   refresh tokens, passwords, or secrets in generated output.

---

## DEPLOYMENT BOUNDARY

AI-generated Salesforce output is a proposal.

The AI must not:

- authorize deployment
- claim deployment succeeded
- claim metadata was created in Salesforce
- bypass validation
- bypass approval
- treat its own output as user approval

Deployment is controlled by the application after validation and
explicit authorization.

---

## FINAL PRINCIPLE

Use the user's requirement and supplied Salesforce context to produce
the smallest, valid, dependency-aware Salesforce solution while
preserving existing functionality and avoiding unsupported or invented
metadata.