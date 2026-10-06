from pathlib import Path
import json


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

    context_json = json.dumps(
        salesforce_context,
        indent=2,
        ensure_ascii=False,
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
""".strip()

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

    context_json = json.dumps(
        salesforce_context,
        indent=2,
        ensure_ascii=False,
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

    context_json = json.dumps(
        salesforce_context,
        indent=2,
        ensure_ascii=False,
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