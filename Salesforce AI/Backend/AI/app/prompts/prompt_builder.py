from pathlib import Path
import json
import re
from Backend.AI.app.services.custom_object_policy import CUSTOM_OBJECT_POLICY_PROMPT


VALIDATION_RULE_FORMULA_RULES = r"""
VALIDATION RULE FORMULAS AND DEPENDENCIES
For REGEX matching a literal plus, prefer [+]. For example:
AND(NOT(ISBLANK(Phone_Number__c)), NOT(REGEX(Phone_Number__c, "^[+]91[0-9]{10}$")))
This example allows blank; include an ISBLANK failure if the requirement forbids blank.
Use the actual discovered API field name. Never copy example field names blindly.
A single backslash before + inside a Salesforce formula string is invalid.
If a regex needs backslashes, escape them for Salesforce formula strings first,
then JSON-encode the complete formula. Do not manually unescape it during conversion.
CDATA affects XML parsing only; it does not fix Salesforce formula-string escaping.
Preserve approved formulas exactly. If an approved formula is invalid, report an
INVALID configuration using an existing issue code such as MISSING_CONFIGURATION;
do not silently change its behavior after approval.
Salesforce context objects are discovered existing objects. plannedComponents
are approved same-plan creates, not evidence that those components exist already.
Rules on same-plan new objects/fields must declare the corresponding dependencies.
Do not reject a declared same-plan dependency solely because it is not yet in org.
""".strip()


FLOW_RESOURCE_NAMING_RULES = """
FLOW INTERNAL NAMES — REQUIRED SELF-CHECK
All element, variable, formula, constant, expression, text-template, choice,
dynamic-choice, decision-rule, scheduled-path and screen-field names share one
namespace. Each must be unique, with no double underscores or trailing underscore.
Screen inputs already expose resources using their own names. Do not declare a
variable with the same name as a screen input. isInput on a variable means a Flow
caller supplies it; it does not make a screen control.
Use distinct names such as Enter_Field_List (Screen), Input_Field_List_Name
(text input), Input_Date_Of_Field (Date input), Create_Field_List_Record (create).
CreateRecords inputAssignments should reference Input_Field_List_Name and
Input_Date_Of_Field directly: {"type":"Reference","value":"Input_Date_Of_Field"}.
Do not use ScreenName.InputName for native screen inputs.
Only internal resource/element names follow these restrictions. Preserve real
Salesforce API names such as Field_List__c and Date_of_Field__c in object and
record-field properties; never strip their __c suffixes.
Before returning JSON, collect every internal name and check for collisions.
Metadata conversion must preserve the approved config, never silently rename it.

FLOW GRAPH SELF-CHECK
Declare every element name before wiring connectors. startElement, next,
faultNext, defaultNext, each Decision rule next, Loop nextValue and scheduled
path next must reference an exact declared element name whenever not null.
Labels are not API names. There is no implicit End/Done/Finish element.
Null ends an ordinary branch; it must not replace a required update or action.
Every element must be reachable from Start or a declared scheduled path.
Do not leave orphaned nodes after changing a branch. Only supported explicit
Loop return edges may form cycles. Preserve all requested branches and actions.

TYPED SALESFORCE RECORD IDS
Every Flow variable that carries a Salesforce record Id must be declared as
dataType String with referenceTo set to the exact Salesforce object API name.
This applies to caller-supplied Id inputs, GetRecords Id outputAssignments,
and variables passed to UpdateRecordById or DeleteRecordById. For example,
accountId and foundId for Account records both use referenceTo: "Account".
An untyped String is not an Account Id. Keep the Id filter, output variable,
and record-operation target typed to the same object. Do not use an SObject
variable when only an Id is requested.

SCHEDULED RECORD PROCESSING
For a requirement to process each matching record on a daily/weekly schedule,
use flowType Scheduled, triggerType Scheduled, object set to the discovered
object API name, schedule set to the requested org-local date/time/timeZone,
and startFilters selecting that population. Salesforce supplies one $Record
per matching record. For updates to that record, use UpdateRecordById with
recordId {"type":"Reference","value":"$Record.Id"}.
Do not query and loop over the same population again inside each interview.
Use an objectless Scheduled Flow only when the requirement calls for one
scheduled interview rather than per-record processing (for example an aggregate).
Loops remain supported for genuinely separate collection-processing requirements.
Loop.next is the after-last-item connector; Loop.nextValue is the loop-body
connector. After the final item, next must name actual remaining work or be null.
Never use "End_Flow", "End", "Done" or "Finish" as an undeclared target.
A loop body must return to its Loop; do not null out its return edge.

SCHEMATIC EXAMPLE — ADAPT ALL API NAMES AND VALUES TO DISCOVERED CONTEXT
For a scheduled status update, use these two elements, not GetRecords + Loop:
{"startElement":"Check_Status","elements":[
 {"kind":"Decision","name":"Check_Status","label":"Check status",
  "defaultLabel":"Already active","defaultNext":null,"rules":[
   {"name":"Needs_Update","label":"Needs update","conditionLogic":"or",
    "conditions":[
     {"field":"$Record.Status__c","operator":"IsNull","value":{"type":"Boolean","value":true}},
     {"field":"$Record.Status__c","operator":"NotEqualTo","value":{"type":"String","value":"Active"}}],
    "next":"Set_Active"}]},
 {"kind":"UpdateRecordById","name":"Set_Active","label":"Set active",
  "object":"Example__c","recordId":{"type":"Reference","value":"$Record.Id"},
  "inputAssignments":[{"field":"Status__c","value":{"type":"String","value":"Active"}}],
  "next":null}]}
This is only a graph example, not a complete config. Include the actual schedule,
object, startFilters, contractVersion and Draft status in the complete config.
Never substitute Example__c for the discovered object.

FLOW NULL CHECKS AND PATH TERMINATION
A Date/DateTime literal must never contain an empty string. Test a missing Date
input with {"field":"newDate","operator":"IsNull","value":{"type":"Boolean","value":true}}.
Use the actual input name. For optional unset variable defaults, omit value;
never substitute today's date or a made-up default. IsNull takes a Boolean
operand regardless of whether the tested resource is Date, String or Number.
An Assignment element requires at least one real assignment. Do not create
placeholder End, Done, or Skip Assignment nodes with assignments: []. End paths
by setting their connector to null (next/defaultNext/rule next as appropriate).
For a scheduled record update, Start selects records, a Decision tests whether
an update is needed, and UpdateRecordById targets $Record.Id. A branch needing
no action ends directly. If testing a nullable Status for a target value,
explicitly include the blank case so those records are not accidentally skipped.
""".strip()


# =========================================================
# Project Paths
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

PROMPT_ENGINEERING_ROOT = (
    PROJECT_ROOT
    / "Prompt Engineering"
)

COMMON_PROMPT_DIR = (
    PROMPT_ENGINEERING_ROOT
    / "Common"
)

PLANNING_PROMPT_DIR = (
    PROMPT_ENGINEERING_ROOT
    / "Planning"
)

METADATA_PROMPT_DIR = (
    PROMPT_ENGINEERING_ROOT
    / "Metadata"
)

CHANGE_PROMPT_DIR = (
    PROMPT_ENGINEERING_ROOT
    / "Change"
)


# =========================================================
# Common Prompt Files
# =========================================================

COMMON_PROMPT_FILES = [
    COMMON_PROMPT_DIR / "salesforce_rules.md",
    COMMON_PROMPT_DIR / "naming_rules.md",
    COMMON_PROMPT_DIR / "security_rules.md",
    COMMON_PROMPT_DIR / "output_rules.md",
]


# =========================================================
# Versioned Prompt Files
# =========================================================

PLANNING_PROMPT_FILE = (
    PLANNING_PROMPT_DIR
    / "requirement_to_plan_v002.md"
)

METADATA_PROMPT_FILE = (
    METADATA_PROMPT_DIR
    / "plan_to_metadata_v001.md"
)

CHANGE_PROMPT_FILE = (
    CHANGE_PROMPT_DIR
    / "plan_to_change_v001.md"
)


# =========================================================
# Generic Prompt File Loader
# =========================================================

def load_prompt_file(
    file_path: Path,
) -> str:

    """
    Load one Prompt Engineering markdown file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {file_path}"
        )

    content = file_path.read_text(
        encoding="utf-8"
    ).strip()

    if not content:
        raise ValueError(
            f"Prompt file is empty: {file_path}"
        )

    return content


# =========================================================
# Load Common Salesforce Rules
# =========================================================

def load_common_rules() -> str:

    """
    Load and combine shared Salesforce AI rules.
    """

    sections = []

    for file_path in COMMON_PROMPT_FILES:

        content = load_prompt_file(
            file_path
        )

        sections.append(
            content
        )

    return "\n\n---\n\n".join(
        sections
    )


# =========================================================
# Load Planning Prompt
# =========================================================

def load_planning_prompt() -> str:

    return load_prompt_file(
        PLANNING_PROMPT_FILE
    )


# =========================================================
# Load Metadata Prompt
# =========================================================

def load_metadata_prompt() -> str:

    return load_prompt_file(
        METADATA_PROMPT_FILE
    )


# =========================================================
# Load Change Prompt
# =========================================================

def load_change_prompt() -> str:

    return load_prompt_file(
        CHANGE_PROMPT_FILE
    )


# =========================================================
# Build Planning Prompt
# =========================================================

def build_planning_prompt(
    requirement: str,
    salesforce_context: dict,
) -> str:

    """
    Build the Salesforce implementation planning prompt.

    Ensures the actual user requirement and Salesforce
    context are separated using explicit markers.

    These markers allow both the real AI provider and
    MockProvider to identify the relevant input.

    Supports uppercase and lowercase placeholders.

    Does not duplicate sections when the planning
    template already supplies their markers.
    """

    # -----------------------------------------------------
    # 1. Validate inputs
    # -----------------------------------------------------

    if (
        not isinstance(requirement, str)
        or not requirement.strip()
    ):
        raise ValueError(
            "Requirement cannot be empty."
        )

    if not isinstance(
        salesforce_context,
        dict,
    ):
        raise ValueError(
            "Salesforce context must be a dictionary."
        )

    # -----------------------------------------------------
    # 2. Load common rules and planning template
    # -----------------------------------------------------

    common_rules = load_common_rules()

    planning_template = (
        load_planning_prompt()
    )

    # -----------------------------------------------------
    # 3. Serialize dynamic inputs
    # -----------------------------------------------------

    requirement_text = (
        requirement.strip()
    )

    from Backend.AI.app.salesforce.context_selector import compact_planning_context
    prompt_context = compact_planning_context(requirement, salesforce_context)
    context_json = json.dumps(
        prompt_context, separators=(",", ":"), ensure_ascii=False,
    )
    import logging
    logging.getLogger(__name__).info(
        "Planning context: objects=%d original_chars=%d compact_chars=%d",
        len(salesforce_context.get("objects", [])),
        len(json.dumps(salesforce_context, ensure_ascii=False)), len(context_json),
    )

    # -----------------------------------------------------
    # 4. Create explicitly marked sections
    # -----------------------------------------------------

    requirement_block = (
        "<USER_REQUIREMENT>\n"
        f"{requirement_text}\n"
        "</USER_REQUIREMENT>"
    )

    context_block = (
        "<SALESFORCE_CONTEXT>\n"
        f"{context_json}\n"
        "</SALESFORCE_CONTEXT>"
    )

    # -----------------------------------------------------
    # 5. Check whether the template already wraps inputs
    # -----------------------------------------------------

    template_has_requirement_tags = (
        "<USER_REQUIREMENT>" in planning_template
        and "</USER_REQUIREMENT>" in planning_template
    )

    template_has_context_tags = (
        "<SALESFORCE_CONTEXT>" in planning_template
        and "</SALESFORCE_CONTEXT>" in planning_template
    )

    # Avoid nested markers when the template already
    # provides its own section wrappers.

    requirement_replacement = (
        requirement_text
        if template_has_requirement_tags
        else requirement_block
    )

    context_replacement = (
        context_json
        if template_has_context_tags
        else context_block
    )

    # -----------------------------------------------------
    # 6. Insert Salesforce context
    # -----------------------------------------------------

    planning_prompt = (
        planning_template
    )

    for placeholder in (
        "{{salesforce_context}}",
        "{{SALESFORCE_CONTEXT}}",
    ):
        planning_prompt = (
            planning_prompt.replace(
                placeholder,
                context_replacement,
            )
        )

    # -----------------------------------------------------
    # 7. Insert user requirement
    # -----------------------------------------------------

    for placeholder in (
        "{{requirement}}",
        "{{REQUIREMENT}}",
    ):
        planning_prompt = (
            planning_prompt.replace(
                placeholder,
                requirement_replacement,
            )
        )

    # -----------------------------------------------------
    # 8. Add missing sections
    #
    # Important for planning templates that contain
    # instructions but do not provide explicit markers.
    # -----------------------------------------------------

    has_context_section = (
        "<SALESFORCE_CONTEXT>" in planning_prompt
        and "</SALESFORCE_CONTEXT>" in planning_prompt
    )

    if not has_context_section:
        planning_prompt += (
            "\n\n"
            + context_block
        )

    has_requirement_section = (
        "<USER_REQUIREMENT>" in planning_prompt
        and "</USER_REQUIREMENT>" in planning_prompt
    )

    if not has_requirement_section:
        planning_prompt += (
            "\n\n"
            + requirement_block
        )

    # -----------------------------------------------------
    # 9. Reject unresolved input placeholders
    # -----------------------------------------------------

    unresolved_placeholders = (
        "{{requirement}}",
        "{{REQUIREMENT}}",
        "{{salesforce_context}}",
        "{{SALESFORCE_CONTEXT}}",
    )

    remaining = [
        placeholder
        for placeholder in unresolved_placeholders
        if placeholder in planning_prompt
    ]

    if remaining:
        raise ValueError(
            "Unresolved planning prompt placeholders: "
            + ", ".join(remaining)
        )

    # -----------------------------------------------------
    # 10. Build final prompt
    # -----------------------------------------------------

    final_prompt = f"""
# COMMON SALESFORCE AI RULES

{common_rules}

---

# ACTIVE TASK

{planning_prompt}

{CUSTOM_OBJECT_POLICY_PROMPT}
""".strip()

    if re.search(r"\bflows?\b", requirement, re.IGNORECASE):
        from Backend.AI.app.validators.flow_validator import flow_config_json_schema
        final_prompt += "\n\n" + FLOW_RESOURCE_NAMING_RULES
        final_prompt += "\n\n<FLOW_CONFIG_SCHEMA>\n" + json.dumps(flow_config_json_schema(), separators=(",", ":")) + "\n</FLOW_CONFIG_SCHEMA>"

    final_prompt += "\n\n" + VALIDATION_RULE_FORMULA_RULES
    return final_prompt


# =========================================================
# Build Metadata Prompt
# =========================================================

def build_metadata_prompt(
    implementation_plan: dict,
    salesforce_context: dict,
) -> str:

    """
    Build the complete Salesforce metadata prompt.

    Contains:
        Common Salesforce Rules
        Metadata Instructions
        Approved Implementation Plan
        Salesforce Context
    """

    if not isinstance(
        implementation_plan,
        dict,
    ):
        raise ValueError(
            "Implementation plan must be a dictionary."
        )

    if not implementation_plan:
        raise ValueError(
            "Implementation plan cannot be empty."
        )

    if not isinstance(
        salesforce_context,
        dict,
    ):
        raise ValueError(
            "Salesforce context must be a dictionary."
        )

    # -----------------------------------------------------
    # 1. Load shared rules
    # -----------------------------------------------------

    common_rules = (
        load_common_rules()
    )

    # -----------------------------------------------------
    # 2. Load metadata-specific prompt
    # -----------------------------------------------------

    metadata_template = (
        load_metadata_prompt()
    )

    # -----------------------------------------------------
    # 3. Serialize implementation plan
    # -----------------------------------------------------

    plan_json = json.dumps(
        implementation_plan,
        indent=2,
        ensure_ascii=False,
    )

    # -----------------------------------------------------
    # 4. Serialize Salesforce context
    # -----------------------------------------------------

    from Backend.AI.app.salesforce.context_selector import compact_planning_context
    context_json = json.dumps(
        compact_planning_context(json.dumps(implementation_plan, default=str), salesforce_context),
        separators=(",", ":"), ensure_ascii=False,
    )

    # -----------------------------------------------------
    # 5. Insert implementation plan
    # -----------------------------------------------------

    metadata_prompt = (
        metadata_template.replace(
            "{{implementation_plan}}",
            plan_json,
        )
    )

    # -----------------------------------------------------
    # 6. Insert Salesforce context
    # -----------------------------------------------------

    metadata_prompt = (
        metadata_prompt.replace(
            "{{salesforce_context}}",
            context_json,
        )
    )

    # -----------------------------------------------------
    # 7. Build final prompt
    # -----------------------------------------------------

    final_prompt = f"""
# COMMON SALESFORCE AI RULES

{common_rules}

---

# ACTIVE TASK

{metadata_prompt}
""".strip()

    if any(item.get("metadataType") == "Flow" for item in implementation_plan.get("items", [])):
        from Backend.AI.app.validators.flow_validator import flow_config_json_schema
        final_prompt += "\n\n" + FLOW_RESOURCE_NAMING_RULES
        final_prompt += "\n\n<FLOW_CONFIG_SCHEMA>\n" + json.dumps(flow_config_json_schema(), separators=(",", ":")) + "\n</FLOW_CONFIG_SCHEMA>"

    final_prompt += "\n\n" + VALIDATION_RULE_FORMULA_RULES
    return final_prompt


# =========================================================
# Build Change Prompt
# =========================================================

def build_change_prompt(
    implementation_plan: dict,
    salesforce_context: dict,
) -> str:

    """
    Build the complete Salesforce change prompt.

    Change v001 is used for safe UPDATE operations
    against existing Salesforce metadata.
    """

    if not isinstance(
        implementation_plan,
        dict,
    ):
        raise ValueError(
            "Implementation plan must be a dictionary."
        )

    if not implementation_plan:
        raise ValueError(
            "Implementation plan cannot be empty."
        )

    if not isinstance(
        salesforce_context,
        dict,
    ):
        raise ValueError(
            "Salesforce context must be a dictionary."
        )

    # -----------------------------------------------------
    # 1. Load shared rules
    # -----------------------------------------------------

    common_rules = (
        load_common_rules()
    )

    # -----------------------------------------------------
    # 2. Load change-specific prompt
    # -----------------------------------------------------

    change_template = (
        load_change_prompt()
    )

    # -----------------------------------------------------
    # 3. Serialize implementation plan
    # -----------------------------------------------------

    plan_json = json.dumps(
        implementation_plan,
        indent=2,
        ensure_ascii=False,
    )

    # -----------------------------------------------------
    # 4. Serialize Salesforce context
    # -----------------------------------------------------

    from Backend.AI.app.salesforce.context_selector import compact_planning_context
    context_json = json.dumps(
        compact_planning_context(json.dumps(implementation_plan, default=str), salesforce_context),
        separators=(",", ":"), ensure_ascii=False,
    )

    # -----------------------------------------------------
    # 5. Insert implementation plan
    # -----------------------------------------------------

    change_prompt = (
        change_template.replace(
            "{{IMPLEMENTATION_PLAN}}",
            plan_json,
        )
    )

    change_prompt = (
        change_prompt.replace(
            "{{implementation_plan}}",
            plan_json,
        )
    )

    # -----------------------------------------------------
    # 6. Insert Salesforce context
    # -----------------------------------------------------

    change_prompt = (
        change_prompt.replace(
            "{{SALESFORCE_CONTEXT}}",
            context_json,
        )
    )

    change_prompt = (
        change_prompt.replace(
            "{{salesforce_context}}",
            context_json,
        )
    )

    # -----------------------------------------------------
    # 7. Check unresolved placeholders
    # -----------------------------------------------------

    unresolved_placeholders = [
        "{{IMPLEMENTATION_PLAN}}",
        "{{implementation_plan}}",
        "{{SALESFORCE_CONTEXT}}",
        "{{salesforce_context}}",
    ]

    remaining_placeholders = [
        placeholder
        for placeholder in unresolved_placeholders
        if placeholder in change_prompt
    ]

    if remaining_placeholders:
        raise ValueError(
            "Unresolved Change prompt placeholder(s): "
            + ", ".join(
                remaining_placeholders
            )
        )

    # -----------------------------------------------------
    # 8. Build final prompt
    # -----------------------------------------------------

    final_prompt = f"""
# COMMON SALESFORCE AI RULES

{common_rules}

---

# ACTIVE TASK

{change_prompt}
""".strip()

    return final_prompt
