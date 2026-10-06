import json

from Backend.AI.app.prompts.prompt_builder import (
    build_change_prompt,
)

from Backend.AI.app.providers.base import (
    AIProvider,
)

from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)

from Backend.AI.app.validators.change_spec_validator import (
    ChangeSpecification,
    validate_change_spec,
)


# =========================================================
# AI Change JSON Parser
# =========================================================

def _parse_change_json(
    response: str,
) -> dict:
    """
    Parse Change Specification JSON returned by the
    AI provider.

    Supports:
    - Raw JSON
    - JSON wrapped inside Markdown code fences

    Arbitrary prose is not silently accepted.
    """

    # -----------------------------------------------------
    # 1. Response must be a string
    # -----------------------------------------------------

    if not isinstance(
        response,
        str,
    ):

        raise ValueError(
            "AI response must be a string."
        )

    cleaned = response.strip()

    # -----------------------------------------------------
    # 2. Response cannot be empty
    # -----------------------------------------------------

    if not cleaned:

        raise ValueError(
            "AI returned an empty response."
        )

    # -----------------------------------------------------
    # 3. Handle Markdown fenced JSON
    #
    # Example:
    #
    # ```json
    # {
    #   ...
    # }
    # ```
    # -----------------------------------------------------

    if cleaned.startswith("```"):

        lines = cleaned.splitlines()

        # Remove opening fence:
        # ``` or ```json
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
    # 4. Parse JSON
    # -----------------------------------------------------

    try:

        parsed = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        preview = cleaned[:500]

        raise ValueError(
            "AI returned invalid change JSON. "
            f"Response starts with: {preview!r}. "
            f"JSON error: {exc}"
        ) from exc

    # -----------------------------------------------------
    # 5. Top-level value must be JSON object
    # -----------------------------------------------------

    if not isinstance(
        parsed,
        dict,
    ):

        raise ValueError(
            "AI change response must be "
            "a JSON object."
        )

    return parsed


# =========================================================
# Change Service
# =========================================================

class ChangeService:
    """
    Converts an APPROVED ImplementationPlan containing
    UPDATE operations into a validated ChangeSpecification.

    The service:

    - validates plan status
    - prepares Salesforce context
    - builds Change v001 prompt
    - sends the task to the configured AI provider
    - parses returned JSON
    - validates the Change Specification
    - verifies the returned planId

    This service does NOT:

    - generate Salesforce XML
    - modify Salesforce metadata files
    - execute Salesforce CLI
    - deploy anything to Salesforce
    """

    def __init__(
        self,
        provider: AIProvider,
    ):

        self.provider = provider

    # =====================================================
    # Generate Change Specification
    # =====================================================

    def generate_specification(
        self,
        plan: ImplementationPlan,
        salesforce_context: dict | None = None,
    ) -> ChangeSpecification:
        """
        Generate a validated Salesforce Change
        Specification from an approved plan.
        """

        # -------------------------------------------------
        # 1. Validate plan status
        # -------------------------------------------------

        if plan.status != "APPROVED":

            raise ValueError(
                "Only APPROVED plans can generate "
                "a change specification."
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

        plan_data = (
            plan.model_dump()
        )

        # -------------------------------------------------
        # 4. Build Change v001 prompt
        # -------------------------------------------------

        final_prompt = build_change_prompt(
            implementation_plan=plan_data,
            salesforce_context=(
                salesforce_context
            ),
        )

        # -------------------------------------------------
        # 5. Build strict system prompt
        #
        # Important:
        # Claude previously responded by explaining its
        # role and asking for the plan/context again.
        #
        # These instructions make it explicit that the
        # required inputs are already provided.
        # -------------------------------------------------

        system_prompt = (
            "You are a Salesforce change "
            "specification engine. "

            "The user prompt already contains BOTH "
            "the approved ImplementationPlan and the "
            "current Salesforce context. "

            "Do not ask the user to provide the plan. "
            "Do not ask the user to provide Salesforce "
            "context. "

            "Do not acknowledge these instructions. "
            "Do not explain your role. "
            "Do not provide introductory text. "
            "Do not provide conclusions. "

            "Process the supplied ImplementationPlan "
            "and Salesforce context immediately. "

            "Generate only safe UPDATE operations "
            "against existing Salesforce metadata. "

            "Do not generate CREATE operations. "
            "Do not generate DELETE operations. "
            "Do not rename metadata API names. "
            "Do not change existing field types. "
            "Do not remove picklist values. "

            "Return exactly one JSON object and "
            "nothing else. "

            "Do not use Markdown. "
            "Do not use code fences. "
            "Do not include commentary before or "
            "after the JSON. "

            "The JSON must conform exactly to "
            "change-spec-v001."
        )

        # -------------------------------------------------
        # 6. Build explicit user prompt
        # -------------------------------------------------

        user_prompt = (
            "Execute the Salesforce Change "
            "Specification task now.\n\n"

            "The approved ImplementationPlan and "
            "current Salesforce context are already "
            "embedded below.\n\n"

            "Do not request additional information.\n"
            "Do not explain the task.\n"
            "Do not acknowledge the instructions.\n"
            "Return JSON only.\n\n"

            f"{final_prompt}"
        )

        # -------------------------------------------------
        # 7. Call configured AI provider
        # -------------------------------------------------

        ai_response = (
            self.provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )

        # -------------------------------------------------
        # 8. Parse AI response
        # -------------------------------------------------

        specification_data = (
            _parse_change_json(
                ai_response
            )
        )

        # -------------------------------------------------
        # 9. Validate Change Specification
        # -------------------------------------------------

        validation = (
            validate_change_spec(
                specification_data
            )
        )

        if not validation.valid:

            raise ValueError(
                "AI generated an invalid change "
                "specification: "
                + "; ".join(
                    validation.errors
                )
            )

        # -------------------------------------------------
        # 10. Convert into typed ChangeSpecification
        # -------------------------------------------------

        specification = (
            ChangeSpecification.model_validate(
                specification_data
            )
        )

        # -------------------------------------------------
        # 11. Verify specification belongs to plan
        # -------------------------------------------------

        if (
            specification.planId
            != plan.id
        ):

            raise ValueError(
                "Change specification planId "
                "does not match the implementation plan."
            )

        # -------------------------------------------------
        # 12. Return validated specification
        # -------------------------------------------------

        return specification