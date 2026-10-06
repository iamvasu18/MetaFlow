import json

from Backend.AI.app.prompts.prompt_builder import (
    build_planning_prompt,
)
from Backend.AI.app.providers.base import AIProvider
from Backend.AI.app.salesforce.context_selector import (
    SalesforceContextSelector,
)
from Backend.AI.app.salesforce.metadata_service import (
    SalesforceMetadataService,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
    validate_plan,
)


# =========================================================
# AI JSON Parser
# =========================================================

def _parse_ai_json(
    response: str,
) -> dict:
    """
    Parse JSON returned by the AI provider.

    Supports:
    - Raw JSON
    - JSON wrapped inside Markdown code fences

    Arbitrary text outside JSON is not silently accepted.
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

        # Remove opening ``` or ```json
        if lines:
            lines = lines[1:]

        # Remove closing ```
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
            "AI returned invalid JSON. "
            f"Response starts with: {preview!r}. "
            f"JSON error: {exc}"
        ) from exc

    # -----------------------------------------------------
    # Planning response must be a JSON object
    # -----------------------------------------------------

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "AI response JSON must be an object."
        )

    return parsed


# =========================================================
# Planning Service
# =========================================================

class PlanningService:
    """
    Coordinates the complete:

    Requirement
        ->
    Salesforce Object Discovery
        ->
    Salesforce Metadata
        ->
    Context Selection
        ->
    Prompt
        ->
    AI
        ->
    Validated Implementation Plan
    """

    def __init__(
        self,
        provider: AIProvider,
        metadata_service: SalesforceMetadataService | None = None,
        context_selector: SalesforceContextSelector | None = None,
    ):
        self.provider = provider

        self.metadata_service = (
            metadata_service
        )

        self.context_selector = (
            context_selector
            or SalesforceContextSelector()
        )

    def _select_salesforce_context(
        self,
        requirement: str,
        salesforce_context: dict,
    ) -> dict:
        """
        Select only Salesforce metadata relevant to
        the user's requirement.
        """

        return self.context_selector.select(
            requirement=requirement,
            metadata=salesforce_context,
        )

    def _build_salesforce_context_from_org(
        self,
        requirement: str,
    ) -> dict:
        """
        Discover relevant Salesforce objects and retrieve
        detailed metadata only for those objects.
        """

        if self.metadata_service is None:
            raise ValueError(
                "Salesforce metadata service is not configured."
            )

        # ---------------------------------------------
        # 1. Find relevant Salesforce objects
        # ---------------------------------------------

        object_names = (
            self.metadata_service.find_relevant_objects(
                requirement=requirement,
            )
        )

        # ---------------------------------------------
        # 2. No matching objects
        # ---------------------------------------------

        if not object_names:
            return {
                "objects": []
            }

        # ---------------------------------------------
        # 3. Retrieve detailed metadata only for
        #    relevant objects
        # ---------------------------------------------

        return self.metadata_service.get_context(
            object_names
        )

    def generate_plan(
        self,
        requirement: str,
        salesforce_context: dict | None = None,
    ) -> ImplementationPlan:

        # ---------------------------------------------
        # 1. Get Salesforce context
        # ---------------------------------------------

        if salesforce_context is None:

            salesforce_context = (
                self._build_salesforce_context_from_org(
                    requirement=requirement,
                )
            )

        # ---------------------------------------------
        # 2. Select relevant metadata
        # ---------------------------------------------

        relevant_context = (
            self._select_salesforce_context(
                requirement=requirement,
                salesforce_context=salesforce_context,
            )
        )

        # ---------------------------------------------
        # 3. Build final planning prompt
        # ---------------------------------------------

        final_prompt = build_planning_prompt(
            requirement=requirement,
            salesforce_context=relevant_context,
        )

        # ---------------------------------------------
        # 4. Call AI provider
        # ---------------------------------------------

        ai_response = self.provider.generate(
            system_prompt=(
                "You are a Salesforce implementation "
                "planning assistant. "
                "Return only valid JSON."
            ),
            user_prompt=final_prompt,
        )

        # ---------------------------------------------
        # 5. Parse AI response
        # ---------------------------------------------

        plan_data = _parse_ai_json(
            ai_response
        )

        # ---------------------------------------------
        # 6. Validate generated plan
        # ---------------------------------------------

        validation = validate_plan(
            plan_data
        )

        if not validation.valid:

            raise ValueError(
                "AI generated an invalid "
                "Salesforce plan: "
                + "; ".join(
                    validation.errors
                )
            )

        # ---------------------------------------------
        # 7. Convert into typed implementation plan
        # ---------------------------------------------

        return ImplementationPlan.model_validate(
            plan_data
        )