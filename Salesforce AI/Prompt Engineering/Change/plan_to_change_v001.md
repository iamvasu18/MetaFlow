# Salesforce Change Specification Prompt

Version: v001

## PURPOSE

Convert an APPROVED Salesforce Implementation Plan containing UPDATE actions
into a safe Salesforce Change Specification.

The supplied Salesforce context is the source of truth for the current state
of Salesforce.

Process the actual Implementation Plan and Salesforce Context supplied at the
end of this prompt.

Return JSON only.


## SUPPORTED ACTION

Change v001 supports only:

- UPDATE

Do not generate changes for:

- CREATE
- DELETE
- NO_CHANGE

CREATE belongs to the metadata creation workflow.

DELETE is unsupported.

NO_CHANGE items must be skipped.


## SUPPORTED METADATA TYPES

Only these metadata types are supported:

- CustomObject
- CustomField


## SUPPORTED CUSTOM OBJECT CHANGES

For CustomObject, only these properties may change:

- label
- pluralLabel


## SUPPORTED CUSTOM FIELD CHANGES

For CustomField, only these changes are supported:

- label
- required
- addPicklistValues


## APPROVAL RULES

The Implementation Plan must have:

status = APPROVED

Every UPDATE item that produces a change must have:

approval = APPROVED

If the overall plan is not approved:

- generate no changes
- return PLAN_NOT_APPROVED in validationIssues

If an UPDATE item is not approved:

- generate no change for that item
- return ITEM_NOT_APPROVED for that item


## EXISTING METADATA RULES

Every UPDATE operation must target metadata that already exists in the
Salesforce context.

For every UPDATE item:

1. Find the target using its exact fullName.
2. Confirm the target exists.
3. Read the existing configuration.
4. Compare the approved requested change with the existing configuration.
5. Generate only the required change.
6. Preserve every unrelated property.

Never invent existing Salesforce metadata.

Never convert UPDATE into CREATE.


## MISSING METADATA

If the target metadata does not exist:

Use validation issue code:

METADATA_NOT_FOUND

Do not create the missing metadata.


## INSUFFICIENT CONTEXT

If the target appears to exist but the supplied context is not sufficient to
determine the current value safely:

Use:

INSUFFICIENT_CONTEXT

Do not guess.


## LABEL CHANGES

A label change must contain:

- from
- to

The `from` value must exactly match Salesforce context.

The `to` value must come from the approved Implementation Plan.


## REQUIRED CHANGES

A required change must contain:

- from
- to

Both values must be booleans.

The `from` value must match Salesforce context.

The `to` value must come from the approved Implementation Plan.


## PICKLIST ADDITIONS

For a Picklist field, Change v001 supports only:

addPicklistValues

Rules:

1. Preserve all existing values.
2. Add only explicitly requested new values.
3. Do not duplicate existing values.
4. Do not remove existing values.
5. Do not rename existing values.
6. Preserve spelling exactly.
7. Do not output existing values as newly added values.


## NO CHANGE REQUIRED

If Salesforce already contains the requested configuration:

- do not generate an UPDATE
- return NO_CHANGE_REQUIRED for the item


## FIELD TYPE SAFETY

Changing an existing Salesforce field type is not supported.

Never change:

- Text to Email
- Email to Text
- Picklist to Text
- Date to another type
- or any other existing field type

Use:

UNSUPPORTED_FIELD_TYPE_CHANGE


## API NAME SAFETY

Never change metadata API names.

The output fullName must exactly match the fullName supplied in Salesforce
context.

Do not rename:

- CustomObject API names
- CustomField API names

Use:

UNSUPPORTED_RENAME


## UNSUPPORTED OPERATIONS

Do not generate:

- metadata deletion
- field type changes
- object API name changes
- field API name changes
- picklist value removal
- picklist value rename
- relationship changes
- formula changes
- validation rule changes
- Flow changes
- Apex changes
- LWC changes
- destructive metadata changes

Use an appropriate validation issue instead.


## MINIMUM CHANGE PRINCIPLE

Generate the smallest possible change required by the approved plan.

Do not:

- redesign the object
- add unrelated metadata
- modify unrelated properties
- infer additional requirements
- add improvements that were not approved


## DEPENDENCIES

Preserve dependencies from the approved Implementation Plan.

Do not invent dependencies.


## OUTPUT CONTRACT

Return exactly one JSON object.

The top-level JSON object must contain exactly:

- planId
- changes
- validationIssues

Each item in `changes` must contain:

- itemId
- action
- metadataType
- fullName
- dependencies
- changes

The action must always be:

UPDATE

metadataType must be one of:

- CustomObject
- CustomField


## CUSTOM OBJECT CHANGE STRUCTURE

For CustomObject, the `changes` object may contain only:

- label
- pluralLabel

A label or pluralLabel change must contain:

- from
- to


## CUSTOM FIELD CHANGE STRUCTURE

For CustomField, the `changes` object may contain only:

- label
- required
- addPicklistValues

A label change must contain:

- from
- to

A required change must contain:

- from
- to

addPicklistValues must be a non-empty array of unique strings.


## VALIDATION ISSUE STRUCTURE

Every validation issue must contain:

- code
- itemId
- message

itemId may be null only when the issue applies to the entire plan.


## ALLOWED VALIDATION ISSUE CODES

Use only:

- PLAN_NOT_APPROVED
- ITEM_NOT_APPROVED
- METADATA_NOT_FOUND
- INSUFFICIENT_CONTEXT
- UNSUPPORTED_ACTION
- UNSUPPORTED_METADATA_TYPE
- UNSUPPORTED_FIELD_TYPE_CHANGE
- UNSUPPORTED_RENAME
- UNSUPPORTED_CHANGE
- NO_CHANGE_REQUIRED
- INVALID_FULL_NAME
- UNRESOLVED_DEPENDENCY


## OUTPUT RULES

Return exactly one valid JSON object.

Do not return:

- Markdown
- code fences
- explanations
- introductions
- conclusions
- comments
- XML
- Salesforce CLI commands
- prose before the JSON
- prose after the JSON

Do not copy instructional examples.

Execute the actual input below.


# =========================================================
# EXECUTION INPUT
# =========================================================

## APPROVED IMPLEMENTATION PLAN

{{IMPLEMENTATION_PLAN}}


## CURRENT SALESFORCE CONTEXT

{{SALESFORCE_CONTEXT}}


# =========================================================
# EXECUTE
# =========================================================

Process the Implementation Plan and Salesforce Context above now.

Do not ask for additional information.

Do not repeat the input.

Return only the Change Specification JSON object.