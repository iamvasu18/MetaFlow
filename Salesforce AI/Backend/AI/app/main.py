from Backend.AI.app.services.page_layout_service import PageLayoutService
import json
from Backend.AI.app.services.profile_fls_service import (
    SystemAdministratorFLSService,
    initialize_deployment_project,
    validate_create_specification,
    component_path,
)
from pathlib import Path
import shutil
import subprocess
import tempfile

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from Backend.AI.app.providers.provider_factory import (
    get_ai_provider,
)

from Backend.AI.app.services.planning_service import (
    PlanningService,
)

from Backend.AI.app.services.plan_store import (
    PlanStore,
)

from Backend.AI.app.services.metadata_spec_store import (
    MetadataSpecStore,
)

from Backend.AI.app.services.change_spec_store import (
    ChangeSpecStore,
)

from Backend.AI.app.services.execution_service import (
    SalesforceExecutionService,
)

from Backend.AI.app.services.metadata_generator import (
    SalesforceMetadataGenerator,
)

from Backend.AI.app.services.metadata_service import (
    MetadataService,
)

from Backend.AI.app.services.change_service import (
    ChangeService,
)

from Backend.AI.app.services.change_generator import (
    SalesforceChangeGenerator,
)

from Backend.AI.app.services.metadata_validator import (
    SalesforceMetadataValidator,
)

from Backend.AI.app.services.deployment_executor import (
    SalesforceDeploymentExecutor,
)

from Backend.AI.app.salesforce.metadata_service import (
    SalesforceMetadataService,
)


# ==================================================
# FastAPI Application
# ==================================================

app = FastAPI(
    title="Salesforce AI Service"
)


# ==================================================
# Development Stores
# ==================================================

plan_store = PlanStore()

metadata_spec_store = (
    MetadataSpecStore()
)

change_spec_store = (
    ChangeSpecStore()
)


# ==================================================
# Request Model
# ==================================================

class PlanRequest(BaseModel):

    requirement: str = Field(
        ...,
        min_length=1,
        description=(
            "Salesforce requirement provided by the user"
        ),
    )

    salesforce_context: dict | None = Field(
        default=None,
        description=(
            "Optional Salesforce org metadata/context. "
            "If omitted, metadata is discovered automatically."
        ),
    )


# ==================================================
# Helper: Determine Objects Needed For UPDATE
# ==================================================

def get_change_object_names(
    plan,
) -> list[str]:
    """
    Determine which Salesforce objects must be described
    for UPDATE items in an implementation plan.
    """

    object_names: set[str] = set()

    for item in plan.items:

        if item.action != "UPDATE":
            continue

        if item.metadataType == "CustomObject":

            object_names.add(
                item.fullName
            )

        elif item.metadataType == "CustomField":

            if "." not in item.fullName:

                raise ValueError(
                    "Invalid CustomField fullName: "
                    f"{item.fullName}"
                )

            object_name = (
                item.fullName.split(
                    ".",
                    1,
                )[0]
            )

            object_names.add(
                object_name
            )

    return sorted(
        object_names
    )


# ==================================================
# Helper: Run Salesforce CLI And Parse JSON
# ==================================================

def run_salesforce_cli_json(
    command: list[str],
) -> dict:
    """
    Execute a Salesforce CLI command safely on Windows and
    return its JSON response.

    The caller must include --json in the command.

    This helper does not invoke any AI provider.
    """

    sf_command = shutil.which(
        "sf"
    )

    if not sf_command:

        raise RuntimeError(
            "Salesforce CLI executable 'sf' "
            "could not be found."
        )

    if not command:

        raise ValueError(
            "Salesforce CLI command cannot be empty."
        )

    normalized_command = [
        sf_command,
        *command[1:],
    ]

    # Execute sf.CMD directly.
    #
    # This is the Windows-safe approach verified against
    # the current Salesforce CLI installation, including
    # paths such as:
    #
    #   C:\\\\\Program Files\\\\\sf\\\\\bin\\\\\sf.CMD
    #
    # subprocess handles the executable path and arguments
    # correctly without an additional cmd.exe quoting layer.
    result = subprocess.run(
        normalized_command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    stdout = (
        result.stdout or ""
    ).strip()

    stderr = (
        result.stderr or ""
    ).strip()

    parsed = None

    if stdout:

        try:

            parsed = json.loads(
                stdout
            )

        except json.JSONDecodeError:

            parsed = None

    if result.returncode != 0:

        error_message = None

        if isinstance(
            parsed,
            dict,
        ):

            error_message = (
                parsed.get(
                    "message"
                )
                or parsed.get(
                    "name"
                )
            )

            nested_result = (
                parsed.get(
                    "result"
                )
            )

            if (
                not error_message
                and isinstance(
                    nested_result,
                    dict,
                )
            ):

                error_message = (
                    nested_result.get(
                        "message"
                    )
                    or nested_result.get(
                        "error"
                    )
                )

        if not error_message:

            error_message = (
                stderr
                or stdout
                or (
                    "Salesforce CLI command failed "
                    f"with exit code "
                    f"{result.returncode}."
                )
            )

        raise RuntimeError(
            str(
                error_message
            )
        )

    if parsed is None:

        if not stdout:

            raise RuntimeError(
                "Salesforce CLI returned no JSON output."
            )

        raise RuntimeError(
            "Salesforce CLI returned invalid JSON output: "
            f"{stdout[:500]}"
        )

    if not isinstance(
        parsed,
        dict,
    ):

        raise RuntimeError(
            "Salesforce CLI returned an unexpected "
            "JSON response."
        )

    return parsed


# ==================================================
# Helper: Metadata Members For UPDATE Retrieval
# ==================================================

def get_change_metadata_members(
    specification,
) -> list[str]:
    """
    Build exact Salesforce Metadata API members from the
    saved ChangeSpecification.

    Exact org API names are preserved, including namespace
    prefixes.
    """

    members: list[str] = []

    for change in specification.changes:

        if change.action != "UPDATE":

            raise ValueError(
                "UPDATE deployment only supports "
                "UPDATE change items."
            )

        if change.metadataType not in {
            "CustomObject",
            "CustomField",
        }:

            raise ValueError(
                "UPDATE deployment does not support "
                f"metadata type "
                f"{change.metadataType}."
            )

        member = (
            f"{change.metadataType}:"
            f"{change.fullName}"
        )

        if member not in members:

            members.append(
                member
            )

    if not members:

        raise ValueError(
            "ChangeSpecification does not contain "
            "any deployable UPDATE metadata."
        )

    return members


# ==================================================
# Root Endpoint
# ==================================================

@app.get("/")
def root():

    return {
        "message": (
            "Salesforce AI Service is running"
        ),
        "status": "success",
    }


# ==================================================
# Health Endpoint
# ==================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
    }


# ==================================================
# Generate Implementation Plan
# ==================================================

@app.post("/api/plan")
def generate_plan(
    request: PlanRequest,
):

    try:

        provider = (
            get_ai_provider()
        )

        salesforce_metadata_service = (
            SalesforceMetadataService(
                target_org="AIOrg"
            )
        )

        planning_service = (
            PlanningService(
                provider=provider,
                metadata_service=(
                    salesforce_metadata_service
                ),
            )
        )

        plan = (
            planning_service.generate_plan(
                requirement=(
                    request.requirement
                ),
                salesforce_context=(
                    request.salesforce_context
                ),
            )
        )

        plan_store.save(
            plan
        )

        # Clear old generated artifacts
        # if the same plan ID is reused.
        metadata_spec_store.delete(
            plan.id
        )

        change_spec_store.delete(
            plan.id
        )

        return plan.model_dump(
            by_alias=True
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to generate Salesforce "
                "implementation plan."
            ),
        ) from exc


# ==================================================
# Get Stored Plan
# ==================================================

@app.get("/api/plans/{plan_id}")
def get_plan(
    plan_id: str,
):

    plan = plan_store.get(
        plan_id
    )

    if plan is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Plan not found: {plan_id}"
            ),
        )

    return plan.model_dump(
        by_alias=True
    )


# ==================================================
# Approve Plan
# ==================================================

@app.post("/api/plans/{plan_id}/approve")
def approve_plan(
    plan_id: str,
):

    try:

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        if plan.status != "DRAFT":

            raise HTTPException(
                status_code=422,
                detail=(
                    "Only DRAFT plans "
                    "can be approved."
                ),
            )

        # =================================================
        # SAFETY GATE
        #
        # Never approve a plan containing unresolved
        # validation errors.
        # =================================================

        blocking_items = []

        for item in plan.items:

            validation = item.validation

            errors = []

            if validation is not None:

                if hasattr(
                    validation,
                    "errors",
                ):

                    errors = (
                        validation.errors
                        or []
                    )

                elif isinstance(
                    validation,
                    dict,
                ):

                    errors = (
                        validation.get(
                            "errors",
                            [],
                        )
                        or []
                    )

            if errors:

                blocking_items.append(
                    {
                        "itemId": item.id,
                        "fullName": item.fullName,
                        "errors": errors,
                    }
                )

        if blocking_items:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Plan cannot be approved "
                        "because it contains unresolved "
                        "validation errors."
                    ),
                    "items": blocking_items,
                },
            )

        # =================================================
        # APPROVE ITEMS
        # =================================================

        for item in plan.items:

            if item.action == "NO_CHANGE":

                item.approval = "SKIPPED"

            else:

                item.approval = "APPROVED"

        # =================================================
        # APPROVE PLAN
        # =================================================

        plan = (
            plan_store.update_status(
                plan_id=plan_id,
                status="APPROVED",
            )
        )

        return plan.model_dump(
            by_alias=True
        )

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# ==================================================
# Reject Plan
# ==================================================

@app.post("/api/plans/{plan_id}/reject")
def reject_plan(
    plan_id: str,
):

    try:

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        if plan.status != "DRAFT":

            raise HTTPException(
                status_code=422,
                detail=(
                    "Only DRAFT plans "
                    "can be rejected."
                ),
            )

        for item in plan.items:

            if item.action == "NO_CHANGE":

                item.approval = "SKIPPED"

            else:

                item.approval = "REJECTED"

        plan = (
            plan_store.update_status(
                plan_id=plan_id,
                status="REJECTED",
            )
        )

        metadata_spec_store.delete(
            plan_id
        )

        change_spec_store.delete(
            plan_id
        )

        return plan.model_dump(
            by_alias=True
        )

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# ==================================================
# Generate CREATE Metadata
# ==================================================

@app.post(
    "/api/plans/{plan_id}/generate-metadata"
)
def generate_metadata(
    plan_id: str,
):

    try:

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        if plan.status != "APPROVED":

            raise HTTPException(
                status_code=422,
                detail=(
                    "Only APPROVED plans can "
                    "generate metadata."
                ),
            )

        unapproved_items = [
            item.id
            for item in plan.items
            if (
                item.action != "NO_CHANGE"
                and
                item.approval != "APPROVED"
            )
        ]

        if unapproved_items:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "All metadata-generating "
                        "items must be APPROVED."
                    ),
                    "items": unapproved_items,
                },
            )

        provider = (
            get_ai_provider()
        )

        ai_metadata_service = (
            MetadataService(
                provider=provider
            )
        )

        specification = (
            ai_metadata_service
            .generate_specification(
                plan=plan,
                salesforce_context={
                    "objects": []
                },
            )
        )

        if specification.validationIssues:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Metadata specification "
                        "contains validation issues."
                    ),
                    "validationIssues": [
                        issue.model_dump()
                        for issue
                        in specification.validationIssues
                    ],
                },
            )

        metadata_generator = (
            SalesforceMetadataGenerator(
                project_root="."
            )
        )

        generated_files = (
            metadata_generator
            .generate_from_specification(
                specification
            )
        )

        metadata_spec_store.save(
            specification
        )

        return {
            "planId": plan.id,
            "status": plan.status,
            "metadataSpecification": (
                specification.model_dump()
            ),
            "generatedFiles": (
                generated_files
            ),
            "message": (
                "Salesforce metadata generated "
                "successfully from validated "
                "AI metadata specification."
            ),
        }

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ==================================================
# Generate UPDATE Change Specification
# ==================================================

@app.post(
    "/api/plans/{plan_id}/generate-change"
)
def generate_change(
    plan_id: str,
):

    try:

        # --------------------------------------------------
        # 1. Retrieve plan
        # --------------------------------------------------

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        # --------------------------------------------------
        # 2. Plan must be APPROVED
        # --------------------------------------------------

        if plan.status != "APPROVED":

            raise HTTPException(
                status_code=422,
                detail=(
                    "Only APPROVED plans can "
                    "generate changes."
                ),
            )

        # --------------------------------------------------
        # 3. Find UPDATE items
        # --------------------------------------------------

        update_items = [
            item
            for item in plan.items
            if item.action == "UPDATE"
        ]

        if not update_items:

            raise HTTPException(
                status_code=422,
                detail=(
                    "Plan does not contain "
                    "any UPDATE items."
                ),
            )

        # --------------------------------------------------
        # 4. UPDATE items must be approved
        # --------------------------------------------------

        unapproved_items = [
            item.id
            for item in update_items
            if item.approval != "APPROVED"
        ]

        if unapproved_items:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "All UPDATE items must "
                        "be APPROVED."
                    ),
                    "items": unapproved_items,
                },
            )

        # --------------------------------------------------
        # 5. Determine Salesforce objects needed
        # --------------------------------------------------

        object_names = (
            get_change_object_names(
                plan
            )
        )

        if not object_names:

            raise HTTPException(
                status_code=422,
                detail=(
                    "No Salesforce objects could "
                    "be determined for UPDATE items."
                ),
            )

        # --------------------------------------------------
        # 6. Retrieve CURRENT AIOrg metadata
        # --------------------------------------------------

        salesforce_metadata_service = (
            SalesforceMetadataService(
                target_org="AIOrg"
            )
        )

        salesforce_context = (
            salesforce_metadata_service
            .get_context(
                object_names
            )
        )

        # --------------------------------------------------
        # 7. Create ChangeService
        # --------------------------------------------------

        provider = (
            get_ai_provider()
        )

        change_service = (
            ChangeService(
                provider=provider
            )
        )

        # --------------------------------------------------
        # 8. Generate ChangeSpecification
        #
        # Claude is called ONCE here.
        # --------------------------------------------------

        specification = (
            change_service
            .generate_specification(
                plan=plan,
                salesforce_context=(
                    salesforce_context
                ),
            )
        )

        # --------------------------------------------------
        # 9. Stop on validation issues
        # --------------------------------------------------

        if specification.validationIssues:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Change specification "
                        "contains validation issues."
                    ),
                    "validationIssues": [
                        issue.model_dump()
                        for issue
                        in specification.validationIssues
                    ],
                },
            )

        # --------------------------------------------------
        # 10. Save exact ChangeSpecification
        #
        # Future deployment must reuse this exact spec.
        # --------------------------------------------------

        change_spec_store.save(
            specification
        )

        # --------------------------------------------------
        # 11. Return preview
        #
        # NO XML changes.
        # NO deployment.
        # --------------------------------------------------

        return {
            "planId": plan.id,
            "status": plan.status,
            "targetOrg": "AIOrg",
            "changeSpecification": (
                specification.model_dump()
            ),
            "message": (
                "Salesforce change specification "
                "generated successfully. "
                "No Salesforce deployment "
                "has been performed."
            ),
        }

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ==================================================
# Real UPDATE Deployment
# ==================================================

@app.post(
    "/api/plans/{plan_id}/deploy-change"
)
def deploy_change(
    plan_id: str,
):
    """
    Deploy an already generated and approved UPDATE
    ChangeSpecification.

    Safety properties:

    - Reuses the exact saved ChangeSpecification.
    - Does NOT call Claude or any AI provider.
    - Retrieves fresh metadata from AIOrg.
    - Applies the saved change to a temporary copy.
    - Runs a Salesforce dry-run first.
    - Performs the real deployment only after dry-run succeeds.
    - Deletes the temporary staging directory automatically.
    """

    try:

        # --------------------------------------------------
        # 1. Retrieve stored plan
        # --------------------------------------------------

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        # --------------------------------------------------
        # 2. Plan must still be APPROVED
        # --------------------------------------------------

        if plan.status != "APPROVED":

            raise HTTPException(
                status_code=422,
                detail=(
                    "Only APPROVED plans can deploy "
                    "Salesforce changes."
                ),
            )

        # --------------------------------------------------
        # 3. Retrieve exact saved ChangeSpecification
        #
        # No AI call is made during deployment.
        # --------------------------------------------------

        specification = (
            change_spec_store.get(
                plan_id
            )
        )

        if specification is None:

            raise HTTPException(
                status_code=422,
                detail=(
                    "No saved change specification "
                    f"exists for {plan_id}. "
                    "Generate the change specification "
                    "before deployment."
                ),
            )

        if (
            specification.planId
            != plan.id
        ):

            raise HTTPException(
                status_code=422,
                detail=(
                    "Stored change specification "
                    "does not match the "
                    "implementation plan."
                ),
            )

        if specification.validationIssues:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Stored change specification "
                        "contains validation issues."
                    ),
                    "validationIssues": [
                        issue.model_dump()
                        for issue
                        in specification.validationIssues
                    ],
                },
            )

        # --------------------------------------------------
        # 4. Confirm every saved change still maps to the
        #    approved plan item.
        # --------------------------------------------------

        plan_items_by_id = {
            item.id: item
            for item in plan.items
        }

        mismatched_items = []

        for change in specification.changes:

            plan_item = (
                plan_items_by_id.get(
                    change.itemId
                )
            )

            if plan_item is None:

                mismatched_items.append(
                    {
                        "itemId": (
                            change.itemId
                        ),
                        "reason": (
                            "Plan item does not exist."
                        ),
                    }
                )

                continue

            if (
                plan_item.action != "UPDATE"
                or plan_item.approval != "APPROVED"
                or plan_item.metadataType
                != change.metadataType
                or plan_item.fullName
                != change.fullName
            ):

                mismatched_items.append(
                    {
                        "itemId": (
                            change.itemId
                        ),
                        "reason": (
                            "Saved change no longer "
                            "matches an APPROVED UPDATE "
                            "plan item."
                        ),
                    }
                )

        if mismatched_items:

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Saved change specification "
                        "does not match the currently "
                        "approved plan."
                    ),
                    "items": mismatched_items,
                },
            )

        # --------------------------------------------------
        # 5. Build exact Metadata API members
        # --------------------------------------------------

        metadata_members = (
            get_change_metadata_members(
                specification
            )
        )

        # --------------------------------------------------
        # 6. Retrieve FRESH current metadata into a temporary
        #    staging directory.
        # --------------------------------------------------

        with tempfile.TemporaryDirectory(
            prefix=(
                f"salesforce-ai-"
                f"{plan_id}-"
            )
        ) as temp_directory:

            staging_root = Path(
                temp_directory
            ).resolve()

            retrieve_command = [
                "sf",
                "project",
                "retrieve",
                "start",
            ]

            for member in metadata_members:

                retrieve_command.extend(
                    [
                        "--metadata",
                        member,
                    ]
                )

            retrieve_command.extend(
                [
                    "--target-org",
                    "AIOrg",
                    "--output-dir",
                    str(
                        staging_root
                    ),
                    "--json",
                ]
            )

            retrieve_result = (
                run_salesforce_cli_json(
                    retrieve_command
                )
            )

            # --------------------------------------------------
            # 7. Apply saved UPDATE specification to the fresh
            #    retrieved copy.
            #
            # SalesforceChangeGenerator performs current-state
            # checks, including duplicate picklist detection.
            # --------------------------------------------------

            change_generator = (
                SalesforceChangeGenerator(
                    project_root=(
                        staging_root
                    )
                )
            )

            modified_files = (
                change_generator.apply(
                    specification
                )
            )

            if not modified_files:

                raise HTTPException(
                    status_code=422,
                    detail=(
                        "The saved change specification "
                        "did not modify any metadata files."
                    ),
                )

            # --------------------------------------------------
            # 8. Resolve and validate every modified staging
            #    path before Salesforce CLI sees it.
            # --------------------------------------------------

            deployment_files = []

            for relative_file in modified_files:

                deployment_file = (
                    staging_root
                    / relative_file
                ).resolve()

                try:

                    deployment_file.relative_to(
                        staging_root
                    )

                except ValueError as exc:

                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Generated UPDATE metadata "
                            "escaped the temporary "
                            "staging directory."
                        ),
                    ) from exc

                if not deployment_file.is_file():

                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Generated UPDATE metadata "
                            "file does not exist: "
                            f"{relative_file}"
                        ),
                    )

                deployment_files.append(
                    deployment_file
                )

            # --------------------------------------------------
            # 9. Salesforce dry-run validation
            # --------------------------------------------------

            dry_run_command = [
                "sf",
                "project",
                "deploy",
                "start",
                "--dry-run",
            ]

            for deployment_file in deployment_files:

                dry_run_command.extend(
                    [
                        "--source-dir",
                        str(
                            deployment_file
                        ),
                    ]
                )

            dry_run_command.extend(
                [
                    "--target-org",
                    "AIOrg",
                    "--wait",
                    "10",
                    "--json",
                ]
            )

            dry_run_result = (
                run_salesforce_cli_json(
                    dry_run_command
                )
            )

            # --------------------------------------------------
            # 10. REAL Salesforce deployment
            #
            # Only reached when:
            # - plan is APPROVED
            # - exact saved spec exists
            # - fresh metadata retrieval succeeded
            # - local change application succeeded
            # - Salesforce dry-run succeeded
            # --------------------------------------------------

            deploy_command = [
                "sf",
                "project",
                "deploy",
                "start",
            ]

            for deployment_file in deployment_files:

                deploy_command.extend(
                    [
                        "--source-dir",
                        str(
                            deployment_file
                        ),
                    ]
                )

            deploy_command.extend(
                [
                    "--target-org",
                    "AIOrg",
                    "--wait",
                    "10",
                    "--json",
                ]
            )

            deployment_result = (
                run_salesforce_cli_json(
                    deploy_command
                )
            )

            return {
                "message": (
                    "Salesforce UPDATE deployment "
                    "completed successfully."
                ),
                "planId": plan.id,
                "status": plan.status,
                "targetOrg": "AIOrg",
                "changeSpecification": (
                    specification.model_dump()
                ),
                "metadataMembers": (
                    metadata_members
                ),
                "modifiedFiles": (
                    modified_files
                ),
                "retrieve": (
                    retrieve_result
                ),
                "dryRun": (
                    dry_run_result
                ),
                "deployment": (
                    deployment_result
                ),
            }

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ==================================================
# Dry-Run Execution
# ==================================================

@app.post(
    "/api/plans/{plan_id}/execute"
)
def execute_plan(
    plan_id: str,
):

    try:

        plan = plan_store.get(
            plan_id
        )

        if plan is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Plan not found: {plan_id}"
                ),
            )

        execution_service = (
            SalesforceExecutionService(
                target_org="AIOrg"
            )
        )

        result = (
            execution_service.dry_run(
                plan
            )
        )

        return result

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ==================================================
# Real CREATE Deployment
# ==================================================

@app.post(
    "/api/plans/{plan_id}/deploy"
)
def deploy_plan(plan_id: str):
    try:
        plan = plan_store.get(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
        if plan.status != "APPROVED":
            raise HTTPException(status_code=422, detail="Only APPROVED plans can be deployed.")
        unapproved_items = [i.id for i in plan.items if i.action != "NO_CHANGE" and i.approval != "APPROVED"]
        if unapproved_items:
            raise HTTPException(status_code=422, detail={"message": "All deployable plan items must be APPROVED.", "items": unapproved_items})
        specification = metadata_spec_store.get(plan_id)
        if specification is None:
            raise HTTPException(status_code=422, detail=f"No metadata specification exists for {plan_id}. Generate metadata before deployment.")
        if specification.planId != plan.id:
            raise HTTPException(status_code=422, detail="Stored metadata specification does not match the implementation plan.")
        if specification.validationIssues:
            raise HTTPException(status_code=422, detail={"message": "Stored metadata specification contains validation issues.", "validationIssues": [i.model_dump() for i in specification.validationIssues]})
        validate_create_specification(plan, specification)

        # Isolate this request. Existing local profile XML is never overwritten
        # or copied into the deployment, and previous plans cannot leak into it.
        with tempfile.TemporaryDirectory(
            prefix="salesforce-admin-fls-",
            ignore_cleanup_errors=True,
        ) as staging:
            initialize_deployment_project(Path.cwd(), staging)
            generator = SalesforceMetadataGenerator(project_root=staging)
            generator.generate_from_specification(specification)
            generated_files = [str(component_path(i.metadataType, i.fullName)) for i in specification.metadata]
            validation_result = SalesforceMetadataValidator(project_root=staging).validate(plan)
            if not validation_result.get("valid", False):
                raise HTTPException(status_code=422, detail={"message": "Metadata validation failed.", "errors": validation_result.get("errors", [])})

            # Use actual generated field XML for Formula/required/type rules.
            fls = SystemAdministratorFLSService(project_root=staging).generate(specification)
            layouts = PageLayoutService(project_root=staging, target_org="AIOrg").generate(specification)
            deployment_files = list(dict.fromkeys(
                Path(path).as_posix()
                for path in generated_files + fls["generatedFiles"] + layouts["generatedFiles"]
            ))
            validation_result = dict(validation_result)
            validation_result["deploymentFiles"] = deployment_files
            validation_result["validatedFiles"] = deployment_files
            validation_result["systemAdministratorFLS"] = fls
            validation_result["pageLayouts"] = layouts
            result = SalesforceDeploymentExecutor(target_org="AIOrg", project_root=staging).deploy(
                plan=plan, validation_result=validation_result,
            )
            if not result.get("success", False):
                raise HTTPException(status_code=502, detail=result)
            return {
                "message": "Salesforce deployment completed.",
                "planId": plan.id,
                "metadataSpecification": specification.model_dump(),
                "generatedFiles": deployment_files,
                "systemAdministratorFLS": fls,
                "pageLayouts": layouts,
                "validation": validation_result,
                "deployment": result,
            }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
