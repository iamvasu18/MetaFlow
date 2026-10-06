import json

from Backend.AI.app.prompts.prompt_builder import (
    build_metadata_prompt,
)
from Backend.AI.app.providers.base import AIProvider
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)
from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
    validate_metadata_spec,
)


# =========================================================
# AI Metadata JSON Parser
# =========================================================

def _parse_metadata_json(
    response: str,
) -> dict:
    """
    Parse metadata JSON returned by the AI provider.

    Supports:
    - Raw JSON
    - JSON wrapped inside Markdown code fences

    Arbitrary prose is not silently accepted.
    """

    if not isinstance(
        response,
        str,
    ):
        raise ValueError(
            "AI response must be a string."
        )

    cleaned = response.strip()

    if not cleaned:
        raise ValueError(
            "AI returned an empty response."
        )

    # -----------------------------------------------------
    # Claude may return:
    #
    # ```json
    # {
    #   ...
    # }
    # ```
    # -----------------------------------------------------

    if cleaned.startswith("```"):

        lines = cleaned.splitlines()

        # Remove opening fence
        if lines:
            lines = lines[1:]

        # Remove closing fence
        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        cleaned = "\n".join(
            lines
        ).strip()

    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    try:

        parsed = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        preview = cleaned[:500]

        raise ValueError(
            "AI returned invalid metadata JSON. "
            f"Response starts with: {preview!r}. "
            f"JSON error: {exc}"
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "AI metadata response must be "
            "a JSON object."
        )

    return parsed


# =========================================================
# Metadata Service
# =========================================================

class MetadataService:
    """
    Converts an approved ImplementationPlan into a
    validated MetadataSpecification using an AI provider.

    This service:

    - builds the metadata prompt
    - calls the AI provider
    - parses the AI response
    - validates the metadata specification

    It does NOT:

    - generate Salesforce XML
    - execute Salesforce CLI
    - deploy metadata
    """

    def __init__(
        self,
        provider: AIProvider,
    ):
        self.provider = provider

    def generate_specification(
        self,
        plan: ImplementationPlan,
        salesforce_context: dict | None = None,
    ) -> MetadataSpecification:
        """
        Generate a validated metadata specification
        from an approved implementation plan.
        """

        # -------------------------------------------------
        # 1. Validate plan status
        # -------------------------------------------------

        if plan.status != "APPROVED":

            raise ValueError(
                "Only APPROVED plans can generate "
                "a metadata specification."
            )

        # -------------------------------------------------
        # 2. Prepare Salesforce context
        # -------------------------------------------------

        if salesforce_context is None:

            salesforce_context = {
                "objects": []
            }

        if not isinstance(
            salesforce_context,
            dict,
        ):

            raise ValueError(
                "Salesforce context must be "
                "a dictionary."
            )

        # -------------------------------------------------
        # 3. Convert Pydantic plan into dictionary
        # -------------------------------------------------

        plan_data = plan.model_dump()

        # -------------------------------------------------
        # 4. Build metadata prompt
        # -------------------------------------------------

        final_prompt = build_metadata_prompt(
            implementation_plan=plan_data,
            salesforce_context=salesforce_context,
        )

        # -------------------------------------------------
        # 5. Call AI provider
        # -------------------------------------------------

        ai_response = self.provider.generate(
            system_prompt=(
                "You are a Salesforce metadata "
                "specification assistant. "
                "Return only valid JSON conforming "
                "to metadata-spec-v001."
            ),
            user_prompt=final_prompt,
        )

        # -------------------------------------------------
        # 6. Parse AI response
        # -------------------------------------------------

        specification_data = (
            _parse_metadata_json(
                ai_response
            )
        )

        # -------------------------------------------------
        # 7. Validate metadata specification
        # -------------------------------------------------

        validation = validate_metadata_spec(
            specification_data
        )

        if not validation.valid:

            raise ValueError(
                "AI generated an invalid metadata "
                "specification: "
                + "; ".join(
                    validation.errors
                )
            )

        # -------------------------------------------------
        # 8. Convert into typed specification
        # -------------------------------------------------

        specification = (
            MetadataSpecification.model_validate(
                specification_data
            )
        )

        # -------------------------------------------------
        # 9. Make sure specification belongs to this plan
        # -------------------------------------------------

        if specification.planId != plan.id:

            raise ValueError(
                "Metadata specification planId "
                "does not match the implementation plan."
            )

        return specification