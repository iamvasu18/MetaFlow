# Salesforce Naming Rules

Rule Set: salesforce_naming
Version: v001
Status: active

## PURPOSE

These rules define naming conventions for Salesforce components
proposed or referenced by Salesforce AI tasks.

The objective is to produce consistent, valid, readable Salesforce
names while preserving names of components that already exist in the
target Salesforce organization.

---

## GENERAL NAMING PRINCIPLES

1. Use the Salesforce API name from the supplied Salesforce context
   whenever referencing an existing component.

2. Never rename an existing Salesforce component simply to make its
   name more consistent or readable.

3. Do not invent a different API name for an existing component.

4. Generate a new API name only when a new component must be created
   and an API name has not already been explicitly supplied.

5. Prefer clear and descriptive names.

6. Avoid unnecessary abbreviations.

7. Avoid ambiguous names.

8. Do not include spaces in Salesforce API names.

9. Preserve capitalization of existing API names exactly as supplied
   by Salesforce context.

---

## STANDARD SALESFORCE COMPONENTS

Standard Salesforce objects and fields must use their existing
Salesforce API names.

Examples:

Account

Contact

Opportunity

Contact.FirstName

Contact.LastName

Contact.Email

Account.Name

Opportunity.CloseDate

Do not append custom suffixes to standard Salesforce components.

Incorrect:

Contact__c

Contact.Email__c

Account.Name__c

Correct:

Contact

Contact.Email

Account.Name

---

## CUSTOM OBJECT NAMES

New custom objects should use a descriptive API name followed by:

__c

Example:

Business label:

Training Session

API name:

Training_Session__c

Another example:

Business label:

Funding Application

API name:

Funding_Application__c

Do not append __c more than once.

Incorrect:

Training_Session__c__c

---

## CUSTOM FIELD NAMES

New custom fields should use a descriptive API name followed by:

__c

Example:

Business label:

Session Date

API name:

Session_Date__c

Example:

Business label:

Preferred Language

API name:

Preferred_Language__c

When representing a field as a full metadata name, use:

ObjectApiName.FieldApiName

Example:

Training_Session__c.Session_Date__c

Contact.Preferred_Language__c

---

## EXISTING CUSTOM COMPONENTS

If Salesforce context contains:

Customer_Detail__c

continue using:

Customer_Detail__c

Do not change it to:

CustomerDetail__c

Customer__c

Customer_Details__c

or any other alternative.

The Salesforce context is authoritative for existing API names.

---

## LABELS AND API NAMES

A Salesforce label and Salesforce API name are different concepts.

Example:

Label:

Preferred Language

API name:

Preferred_Language__c

Do not use a human-readable label where an API name is required.

Do not expose API-name formatting unnecessarily when a human-readable
label is specifically requested.

---

## API NAME GENERATION

When generating an API name for a new component:

1. Start from the business label.

2. Remove leading and trailing whitespace.

3. Replace spaces between words with underscores when appropriate.

4. Remove characters that are unsuitable for Salesforce API names.

5. Preserve meaningful words.

6. Apply the correct Salesforce custom suffix where required.

Example:

Customer Status

becomes:

Customer_Status__c

Example:

Application Review

becomes:

Application_Review__c

---

## RELATIONSHIP FIELD NAMES

New custom relationship fields must follow custom field naming
conventions.

Example:

Customer

may become:

Customer__c

when creating a custom lookup or master-detail field.

The relationship target must be explicitly supported by the
requirement or Salesforce context.

Do not invent relationships solely from similar object names.

---

## FLOW NAMES

Flow API names should be descriptive of the business process.

Prefer names such as:

Create_Follow_Up_Task

Update_Application_Status

Notify_Contract_Owner

Avoid vague names such as:

Flow1

NewFlow

TestFlow

MyFlow

If a Flow already exists, use the API name supplied in Salesforce
context exactly.

---

## VALIDATION RULE NAMES

Validation Rule names should describe the condition being enforced.

Examples:

Require_Close_Date

Prevent_Negative_Amount

Require_Email_For_Active_Contact

Avoid generic names such as:

Rule1

Validation1

NewRule

---

## APEX CLASS NAMES

New Apex class names should use PascalCase.

Examples:

AppointmentService

ContractAuthorizationService

FundingApplicationController

Avoid:

appointment_service

MyClass

Class1

NewClass

Existing Apex class names must be preserved exactly.

---

## APEX TRIGGER NAMES

Trigger names should clearly identify the relevant object and purpose.

Examples:

AppointmentTrigger

ContractTrigger

FundingApplicationTrigger

Avoid generic names such as:

Trigger1

NewTrigger

TestTrigger

Do not create multiple triggers for the same object without a clear
architectural requirement.

---

## PERMISSION SET NAMES

Permission Set API names should describe the access being granted.

Examples:

Funding_Application_Reviewer

Contract_Management_User

Survey_Administrator

Do not use vague names such as:

Permission1

NewPermission

Access

---

## RECORD TYPE NAMES

Record Type names should describe the business classification.

Examples:

Vendor_Contract

Customer_Contract

External_Application

Use existing Record Type API names exactly when they are supplied in
Salesforce context.

---

## NAME COLLISION RULES

Before proposing a name for a new component:

1. Check the supplied Salesforce context.

2. Do not create a component with an API name that already belongs to
   another component of the same relevant type.

3. If a component with the required name already exists, determine
   whether NO_CHANGE or UPDATE is appropriate instead of CREATE.

4. Do not solve a naming collision by silently inventing a different
   business concept.

5. If the correct name cannot be determined safely, report the
   ambiguity according to the task's output format.

---

## USER-SUPPLIED API NAMES

If the user explicitly provides a Salesforce API name, preserve it
unless it is clearly incompatible with the requested component type.

Do not silently rewrite user-supplied API names.

If the supplied name appears invalid or ambiguous, report the issue
instead of silently changing it.

---

## NAMING AND CURRENT STATE

General Salesforce naming conventions may be used to generate names
for NEW components.

They must not be used to guess the names of EXISTING components.

Example:

The requirement says:

"Use Customer Status."

If Salesforce context does not identify a corresponding field, do not
claim that Customer_Status__c already exists merely because that would
be a conventional API name.

A generated API name for a proposed CREATE operation and an API name
confirmed to exist in Salesforce are different concepts.

---

## FINAL PRINCIPLE

Preserve existing Salesforce API names exactly.

Generate new names only when new metadata is required.

Generated names must be descriptive, consistent with Salesforce
conventions, and traceable to the user's business requirement.