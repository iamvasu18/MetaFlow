from Backend.AI.app.services.planning_clarification import planning_error_detail
from Backend.AI.app.account_api import router as account_router, account_guard, target_org
from Backend.AI.app.services.layout_selection_service import LayoutSelectionWorkflow
from Backend.AI.app.services.page_layout_service import PageLayoutService
import json
import logging
import time
from Backend.AI.app.services.observability import (
    configure_logging,
    log_event,
    RequestLoggingMiddleware,
)
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

from fastapi import FastAPI, HTTPException, Request
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
    load_metadata_generation_context,
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
app.include_router(account_router)
app.middleware("http")(account_guard)
configure_logging()
app.add_middleware(RequestLoggingMiddleware)


# ==================================================
# Development Stores
# ==================================================

plan_store = PlanStore()
layout_workflow = LayoutSelectionWorkflow(plan_store, project_root=Path.cwd(), target_org="request-scoped")
app.include_router(layout_workflow.router)

# Independent LWC service; existing Flow and metadata endpoints are preserved.
from Backend.AI.app.api.lwc_api import LWCWorkflow
lwc_workflow = LWCWorkflow(project_root=Path.cwd())
app.include_router(lwc_workflow.router)

from Backend.AI.app.api.apex_api import ApexWorkflow
apex_workflow = ApexWorkflow(project_root=Path.cwd())
app.include_router(apex_workflow.router)

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
    job_key: str | None = Field(default=None,pattern=r'^[A-Za-z0-9_-]{16,64}$')
    conversation_id: str | None = Field(default=None,max_length=100)
    repair_ticket: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    repair_error: str | None = Field(default=None,max_length=12000)
    generate_files: bool = False
    target_org: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9_.@+\-]{0,199}$")

    requirement: str = Field(
        ...,
        min_length=1,
        max_length=40000,
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


class DefaultApprovalRequest(BaseModel):
    source_hash: str = Field(min_length=64,max_length=64)


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

    from Backend.AI.app.services.sf_process import sf_arguments
    normalized_command = sf_arguments(normalized_command)
    result = subprocess.run(
        normalized_command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
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

@app.get("/api/flows/capabilities")
def get_flow_capabilities():
    from Backend.AI.app.validators.flow_validator import ExtendedFlowConfig
    schema = ExtendedFlowConfig.model_json_schema()
    fields = schema["$defs"]["ScreenField"]["properties"]
    return {
        "contractVersion": 2,
        "deploymentStatus": "Draft",
        "flowTypes": schema["properties"]["flowType"]["enum"],
        "elements": sorted(schema["properties"]["elements"]["items"]["discriminator"]["mapping"]),
        "screenControls": fields["fieldType"]["enum"],
        "screenInputTypes": fields["dataType"]["anyOf"][0]["enum"],
        "schemaEndpoint": "/api/flows/config-schema",
        "targetOrgValidationRequired": True,
        "activationImplemented": False,
        "unsupported": ["Flow Orchestration", "Specialized industry process types", "Wait elements",
                        "Transform", "Collection processors", "Apex-defined resource types",
                        "Nested loops", "Custom LWC generation", "Automatic Flow launch placement"],
    }


@app.get("/api/flows/config-schema")
def get_flow_config_schema():
    from Backend.AI.app.validators.flow_validator import flow_config_json_schema
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **flow_config_json_schema()}


from Backend.AI.app.services.conversation_service import ConversationTurn


@app.post("/api/workspace/respond")
def respond_to_workspace(request: ConversationTurn):
    if request.target_org != target_org():
        raise HTTPException(403, 'Select your connected workspace org.')
    from Backend.AI.app.services.conversation_service import respond
    from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
    def api_factory():
        transport = owned_metadata_api(request.target_org, default_pipeline.version())
        return transport.api if transport is not None else None
    try:
        return respond(request, get_ai_provider(), api_factory)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/plan")
def generate_plan(
    request: PlanRequest,
    http_request: Request = None,
):
    if request.generate_files:
        if request.target_org != target_org():
            raise HTTPException(403, 'The requested org does not match your authenticated workspace org.')
        from Backend.AI.app.services.background_jobs import enabled, enqueue
        if enabled():
            from fastapi.responses import JSONResponse
            payload={'request':request.model_dump(exclude={'job_key','conversation_id','salesforce_context'}),'conversation_id':request.conversation_id}
            return JSONResponse(enqueue('generate',payload,key=request.job_key),status_code=202)
        try:
            provider=get_ai_provider()
            if request.repair_ticket:
                from Backend.AI.app.account_api import current_account
                from Backend.AI.app.account_api import db
                from Backend.AI.app.services.plan_revision_service import RepairProvider
                with db() as c:
                    row=c.execute('SELECT payload FROM repair_tickets WHERE id=? AND user_id=? AND org_id=?',
                        (request.repair_ticket,current_account.get(),target_org())).fetchone()
                failure=json.loads(row['payload']) if row else None
                if not failure:
                    raise HTTPException(409, 'The saved rejected draft expired or is unavailable. Generate the requirement again to capture its current failure.')
                if failure['originalRequirement'] != request.requirement:
                    raise HTTPException(409, 'The requirement changed. Generate a new draft rather than repair the previous one.')
                provider = RepairProvider(provider, failure)
            elif request.repair_error:
                from Backend.AI.app.services.plan_revision_service import RepairProvider
                raise HTTPException(409,'No saved candidate is available for targeted repair. Generate the requirement once to capture the failing component.')
            return build_default_draft(request.requirement,request.target_org,provider,http_request)
        except HTTPException:raise
        except ValueError as exc:raise HTTPException(422,planning_error_detail(exc)) from exc
        except RuntimeError as exc:raise HTTPException(502,str(exc)) from exc
    require_legacy_workflow()
    if request.target_org != target_org():
        raise HTTPException(422,'The selected org does not match the connected org.')


    try:

        provider = (
            get_ai_provider()
        )

        salesforce_metadata_service = (
            SalesforceMetadataService(
                target_org=target_org()
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

        logging.getLogger(__name__).exception(
            "Failed to generate Salesforce implementation plan"
        )

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

    if metadata_spec_store.get_package(plan_id):
        return default_package_response(plan_id)

    return plan.model_dump(
        by_alias=True
    )


# ==================================================
# Approve Plan
# ==================================================

@app.post("/api/plans/{plan_id}/approve")
@layout_workflow.locked
def approve_plan(
    plan_id: str,
    request: DefaultApprovalRequest | None = None,
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

        layout_workflow.require(plan)

        package=metadata_spec_store.get_package(plan_id)
        if not package:
            require_legacy_workflow()
        if package:
            layout_workflow.options(plan_id)
            default_pipeline.verify_package(package)
            default_pipeline.assert_plan(package,plan)
            if not package.get('layoutReady') or package['layoutSelections']!=layout_workflow.require(plan):
                raise HTTPException(409,'Generate the reviewed files after completing layout selections.')
            if request is None or request.source_hash!=package['sourceHash']:
                raise HTTPException(422,'Approval must identify the exact reviewed source hash.')
            if package.get('state') != 'validated' or package.get('validatedHash') != package['sourceHash']:
                raise HTTPException(409,'Wait for Salesforce validation of these exact files before approving.')

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

        if package:
            package['approvedHash']=package['sourceHash']
            metadata_spec_store.save_package(package)
            return default_package_response(plan_id)

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

        rejected_package=metadata_spec_store.get_package(plan_id)
        if rejected_package:
            rejected_package.update(state='rejected',approvedHash=None,validatedHash=None)
            metadata_spec_store.save_package(rejected_package)
        else:
            metadata_spec_store.delete(plan_id)

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
@layout_workflow.locked
def generate_metadata(
    plan_id: str,
):

    package=metadata_spec_store.get_package(plan_id)
    if package:
        plan=plan_store.get(plan_id)
        try:
            if plan.status=='DRAFT':
                revision_package(plan_id)
                package=default_pipeline.prepare_review(package,plan,layout_workflow.require(plan))
                metadata_spec_store.save_package(package)
            return validate_generated_draft(plan_id)
        except ValueError as exc:raise HTTPException(422,planning_error_detail(exc)) from exc

    require_legacy_workflow()

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
                salesforce_context=load_metadata_generation_context(
                    plan, SalesforceMetadataService(target_org=target_org())
                ),
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


def require_legacy_workflow():
    import os
    if os.getenv('APP_ENABLE_LEGACY_WORKFLOW', '').lower() != 'true':
        raise HTTPException(409, 'Legacy workflow execution is disabled. Use unified workspace source review, validation and deployment.')


# ==================================================
# Generate UPDATE Change Specification
# ==================================================

@app.post(
    "/api/plans/{plan_id}/generate-change"
)
@layout_workflow.locked
def generate_change(
    plan_id: str,
):

    require_legacy_workflow()

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
                target_org=target_org()
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
            "targetOrg": target_org(),
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
@layout_workflow.locked
def deploy_change(
    plan_id: str,
):
    """
    Deploy an already generated and approved UPDATE
    ChangeSpecification.

    Safety properties:

    - Reuses the exact saved ChangeSpecification.
    - Does NOT call Claude or any AI provider.
    - Retrieves fresh metadata from the connected org.
    - Applies the saved change to a temporary copy.
    - Runs a Salesforce dry-run first.
    - Performs the real deployment only after dry-run succeeds.
    - Deletes the temporary staging directory automatically.
    """

    require_legacy_workflow()

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
                    target_org(),
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
                    target_org(),
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
                    target_org(),
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
                "targetOrg": target_org(),
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
@layout_workflow.locked
def execute_plan(
    plan_id: str,
):

    require_legacy_workflow()

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
                target_org=target_org()
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
@layout_workflow.locked
def deploy_plan(plan_id: str, request: DefaultApprovalRequest | None = None):
    package=getattr(metadata_spec_store,'get_package',lambda _:None)(plan_id)
    if package:
        if request is None or request.source_hash != package['sourceHash']:
            raise HTTPException(409,'The displayed files changed. Reload and approve the current version before deploying.')
        return run_default_package(plan_id,dry_run=False)
    require_legacy_workflow()

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
        layout_selections = layout_workflow.require(plan)
        from Backend.AI.app.services.flow_preflight_service import FlowPreflightService
        flow_preflight = FlowPreflightService(target_org=target_org()).validate(plan)

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
            layouts = PageLayoutService(project_root=staging, target_org=target_org()).generate(specification, selections=layout_selections)
            deployment_files = list(dict.fromkeys(
                Path(path).as_posix()
                for path in generated_files + fls["generatedFiles"] + layouts["generatedFiles"]
            ))
            validation_result = dict(validation_result)
            validation_result["deploymentFiles"] = deployment_files
            validation_result["validatedFiles"] = deployment_files
            validation_result["systemAdministratorFLS"] = fls
            validation_result["pageLayouts"] = layouts
            flow_preflight["salesforceValidation"] = FlowPreflightService(target_org=target_org()).validate_generated(
                plan, validation_result, staging,
            )
            result = SalesforceDeploymentExecutor(target_org=target_org(), project_root=staging).deploy(
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
                "flowPreflight": flow_preflight,
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



# Apex/LWC are internal generators of the existing default plan workflow.
from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline
default_pipeline=DefaultMetadataPipeline(project_root=Path.cwd())


def default_package_response(plan_id):
    package=metadata_spec_store.get_package(plan_id)
    if package is None:raise HTTPException(404,'Generated package not found.')
    package['id']=plan_id
    package['plan']=plan_store.get(plan_id).model_dump()
    package['layoutOptions']=layout_workflow.options(plan_id)
    return package


def save_default_result(plan_id,package,payload,operation):
    details=payload.get('result',{})
    if not isinstance(details,dict):raise RuntimeError('Invalid Salesforce deployment response.')
    if package.get('jobId') and details.get('id') != package['jobId']:
        raise ValueError('Salesforce report job identity does not match this saved operation. No result was applied.')
    pending=details.get('done') is False or details.get('status') in {'Pending','Queued','InProgress','Canceling'}
    if pending:state='pending'
    elif details.get('done') is True and details.get('success') is True:
        state='validated' if operation=='validate' else 'deployed'
    elif details.get('done') is True and details.get('success') is False:state='failed'
    else:state='unknown'
    # A successful check-only job simulates component creation; its IDs and
    # componentSuccesses are not evidence that metadata was committed.
    if state == 'deployed' and details.get('checkOnly') is not False:
        state = 'unknown'
        package.update(
            error='Salesforce returned a validation-only result or did not confirm checkOnly=false. Deployment is not confirmed.',
            nextAction='Inspect Salesforce Deployment Status and the saved job ID. Do not repeat deployment until the submitted job is identified.',
        )
    elif state == 'validated' and details.get('checkOnly') is False:
        state = 'unknown'
        package.update(
            error='Salesforce returned a real deployment result for a validation operation. Inspect Deployment Status.',
            nextAction='Review the saved Salesforce job before continuing.',
        )
    # Invalidate whenever Salesforce confirms a real deployment, even when a
    # subsequent application-level test/coverage check rejects its report.
    if details.get('done') is True and details.get('success') is True and details.get('checkOnly') is False:
        from Backend.AI.app.account_api import current_account
        from Backend.AI.app.services.planning_performance import invalidate_org_context
        invalidate_org_context(current_account.get(), package['targetOrg'])
    try:
        default_pipeline.check_tests(package,payload)
    except ValueError as exc:
        package.update(lastResult=payload,operation=operation,jobId=details.get('id'),
            state='failed' if details.get('done') is True and details.get('success') is False else ('failed' if operation=='validate' else 'unknown'),error=str(exc),validatedHash=None)
        metadata_spec_store.save_package(package)
        return default_package_response(plan_id)
    if operation == 'validate':
        package['validatedHash'] = package['sourceHash'] if state == 'validated' else None
    package.update(lastResult=payload,operation=operation,jobId=details.get('id'),state=state)
    if state in {'validated','deployed','failed'} and package.get('operationStartedAt'):
        import time
        elapsed=time.time()-package['operationStartedAt']
        package['operationSeconds']=round(elapsed,3)
        log_event(logging.getLogger(__name__), 'salesforce_operation_finished', operation=operation, state=state, phase='completion', duration_ms=round(elapsed*1000,3), plan_id=plan_id, salesforce_job_id=details.get('id'))
    metadata_spec_store.save_package(package)
    return default_package_response(plan_id)


@layout_workflow.locked
def run_default_package(plan_id,dry_run):
    package=metadata_spec_store.get_package(plan_id)
    if package is None:raise HTTPException(404,'Generated package not found.')
    if package['targetOrg'] != target_org():raise HTTPException(403,'This package belongs to a different org.')
    plan=plan_store.get(plan_id)
    if not dry_run and (plan.status!='APPROVED' or any(i.approval!='APPROVED' for i in plan.items if i.action!='NO_CHANGE') or package.get('approvedHash') != package['sourceHash']):
        raise HTTPException(422,'Approve every deployable plan item first.')
    if package['state'] in {'queued','running','pending','unknown','deployed'}:
        raise HTTPException(409,'Inspect the saved operation before retrying.')
    if not dry_run and (package['state'] != 'validated' or package.get('validatedHash') != package['sourceHash']):
        raise HTTPException(409,'Run Salesforce validation on the approved files before deployment.')
    try:
        default_pipeline.verify_package(package)
        default_pipeline.assert_plan(package,plan)
        if not package.get('layoutReady') or package['layoutSelections']!=layout_workflow.require(plan):raise ValueError('Reviewed layout selections changed.')
    except ValueError as exc:raise HTTPException(422,planning_error_detail(exc)) from exc
    if dry_run and package['state'] == 'validated' and package.get('validatedHash') == package['sourceHash']:
        return default_package_response(plan_id)
    operation='validate' if dry_run else 'deploy'
    import time
    from Backend.AI.app.services.background_jobs import enabled, enqueue
    if enabled():
        enqueue(operation,{'plan_id':plan_id,'source_hash':package['sourceHash']},package=package)
        return default_package_response(plan_id)
    package.update(state='running',operation=operation,error=None,errorDetails=None,nextAction=None,jobId=None,lastResult=None,operationSeconds=None,operationStartedAt=time.time())
    if dry_run:
        package['validatedHash']=None
    metadata_spec_store.save_package(package)
    try:
        payload=default_pipeline.deploy(package,dry_run=dry_run)
        return save_default_result(plan_id,package,payload,operation)
    except ValueError as exc:
        package.update(state='unknown' if operation=='deploy' else 'failed',operation=operation,error=str(exc))
        metadata_spec_store.save_package(package)
        raise HTTPException(422,planning_error_detail(exc)) from exc
    except Exception as exc:
        logging.getLogger(__name__).exception('Salesforce %s failed for plan %s',operation,plan_id)
        # Preserve the CLI's diagnostic rather than replacing every failure
        # with the same outcome warning. Redact common credential forms.
        import re
        diagnostic=re.sub(r'(?i)(Bearer\s+)[^\s]+',r'\1[redacted]',str(exc))
        diagnostic=re.sub(r'(?i)((?:access_token|refresh_token|password|client_secret)\s*[=:]\s*)[^\s,;]+',r'\1[redacted]',diagnostic)
        package.update(state='unknown',operation=operation,
            error='Salesforce did not confirm the '+operation+' result. '+diagnostic[:1500],
            errorDetails={'type':type(exc).__name__,'message':diagnostic[:1500]},
            nextAction='Check the saved job status before retrying. If no job ID was returned, review Salesforce Deployment Status and the backend log.')
        metadata_spec_store.save_package(package)
        raise HTTPException(502,package['error']) from exc


@app.post('/api/plans/{plan_id}/validate')
@layout_workflow.locked
def validate_default_package(plan_id:str):
    return run_default_package(plan_id,dry_run=True)


@app.post('/api/plans/{plan_id}/report')
@layout_workflow.locked
def report_default_package(plan_id:str):
    package=metadata_spec_store.get_package(plan_id)
    if not package or not package.get('jobId'):
        raise HTTPException(409,'No saved Salesforce job ID. Inspect Salesforce Deployment Status.')
    if package['state'] not in {'pending','unknown','failed'}:
        return default_package_response(plan_id)
    try:
        return save_default_result(plan_id,package,default_pipeline.report(package),package['operation'])
    except ValueError as exc:raise HTTPException(422,planning_error_detail(exc)) from exc


class RevisionRequest(BaseModel):
    requirement:str=Field(min_length=1,max_length=20000)


class PermissionAssignmentRequest(BaseModel):
    component_name: str = Field(min_length=1,max_length=80)
    source_hash: str = Field(min_length=64,max_length=64)
    username: str = Field(min_length=1,max_length=320)
    confirmed: bool = False


@app.post('/api/plans/{plan_id}/assign-permission-set')
@layout_workflow.locked
def assign_default_permission_set(plan_id:str,request:PermissionAssignmentRequest):
    from Backend.AI.app.account_api import current_account,current_org,record_activity
    from Backend.AI.app.services.permission_set_service import PermissionAssignmentService
    from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
    package=metadata_spec_store.get_package(plan_id)
    if not package:raise HTTPException(404,'Saved package not found.')
    if package.get('targetOrg')!=current_org.get():raise HTTPException(403,'Select the saved target org.')
    if request.source_hash!=package.get('sourceHash') or package.get('approvedHash')!=package.get('sourceHash'):raise HTTPException(409,'Review the exact deployed source before assigning access.')
    try:
        default_pipeline.verify_package(package)
        transport=owned_metadata_api(package['targetOrg'],package['apiVersion'])
        if not transport:raise ValueError('An authenticated Salesforce connection is required.')
        outcome=PermissionAssignmentService(transport).assign(package,request.component_name,request.username,request.confirmed,metadata_spec_store.save_package)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    if not outcome.get('alreadyAssigned'):
        from Backend.AI.app.services.planning_performance import invalidate_org_context
        invalidate_org_context(current_account.get(),package['targetOrg'])
    record_activity(current_account.get(),package['targetOrg'],plan_id,'permission_set_assignment_checked' if outcome.get('alreadyAssigned') else 'permission_set_assigned','Permission Set assignment confirmed',request.component_name)
    return dict(default_package_response(plan_id),assignmentResult=outcome)


class FlowActivationRequest(BaseModel):
    component_name:str=Field(min_length=1,max_length=80)
    source_hash:str=Field(min_length=64,max_length=64)


@app.post('/api/plans/{plan_id}/activate-flow')
@layout_workflow.locked
def activate_default_flow(plan_id:str,request:FlowActivationRequest):
    from Backend.AI.app.account_api import current_account,current_org,record_activity
    from Backend.AI.app.services.flow_activation_service import FlowActivationService
    package=metadata_spec_store.get_package(plan_id)
    if not package:raise HTTPException(404,'Deployed package not found.')
    if package.get('targetOrg')!=current_org.get():raise HTTPException(403,'Select the saved target org.')
    if request.source_hash!=package.get('sourceHash') or package.get('approvedHash')!=package.get('sourceHash'):raise HTTPException(409,'The approved source does not match this request.')
    previously_active=package.get('flowActivations',{}).get(request.component_name,{}).get('state')=='active'
    try:
        default_pipeline.verify_package(package)
        FlowActivationService(current_account.get(),package['targetOrg'],package['apiVersion']).activate(package,request.component_name,metadata_spec_store.save_package)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    state=package.get('flowActivations',{}).get(request.component_name,{})
    if state.get('state') in {'active','unknown'}:
        from Backend.AI.app.services.planning_performance import invalidate_org_context
        invalidate_org_context(current_account.get(),package['targetOrg'])
        if state.get('state')=='active' and not previously_active:
            record_activity(current_account.get(),package['targetOrg'],plan_id,'flow_activated','Flow activation confirmed',request.component_name)
    return default_package_response(plan_id)


class RepairRequest(BaseModel):
    component_name:str=Field(default='',max_length=200)
    instruction:str=Field(default='',max_length=12000)
    source_hash:str | None=Field(default=None,min_length=64,max_length=64)


class SourceEditRequest(BaseModel):
    component_name:str=Field(min_length=1,max_length=200)
    source_hash:str=Field(min_length=64,max_length=64)
    files:dict[str,str]


def validate_generated_draft(plan_id):
    """Validate the exact saved draft without granting deployment approval."""
    package = metadata_spec_store.get_package(plan_id)
    if not package or not package.get('layoutReady'):
        return default_package_response(plan_id)
    if package.get('state') in {'queued','running','pending','unknown','deployed'}:
        return default_package_response(plan_id)
    try:
        return run_default_package(plan_id, dry_run=True)
    except HTTPException:
        # run_default_package persists submitted-operation failure evidence.
        # Preflight failures have no job; keep them reviewable for repair.
        package = metadata_spec_store.get_package(plan_id)
        if package.get('state') == 'generated':
            import sys
            failure = sys.exc_info()[1]
            detail = failure.detail
            package.update(state='failed', operation='validate', validatedHash=None,
                           error=detail.get('message', str(detail)) if isinstance(detail,dict) else str(detail))
            metadata_spec_store.save_package(package)
        return default_package_response(plan_id)


def build_default_draft(requirement,org,provider,http_request=None,activity_title=None,repair_package=None):
    from time import perf_counter
    draft_started=perf_counter()
    from Backend.AI.app.services.metadata_service import DefaultGenerationRequest
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    from Backend.AI.app.account_api import user,db,save_chat,record_activity
    from Backend.AI.app.services.implementation_routing import resolve_ui_requirement
    requirement = resolve_ui_requirement(requirement)
    package=default_pipeline.generate(DefaultGenerationRequest(requirement=requirement,target_org=org),provider)
    if repair_package:
        old=repair_package
        package['plan']['id']=old['plan']['id']
        if package.get('metadataSpecification'):
            package['metadataSpecification']['planId']=old['plan']['id']
        changed=getattr(provider,'changed_ids',set())
        original_items={i['id']:i for i in old['plan']['items']}
        if {i['id'] for i in package['plan']['items']} != set(original_items):
            raise ValueError('Repair changed the original plan component set.')
        for item in package['plan']['items']:
            before=original_items[item['id']]
            for key in set(item)|set(before):
                if key not in {'config','approval'} and item.get(key)!=before.get(key):
                    raise ValueError('Repair changed original plan intent: '+key)
            if item['id'] not in changed:item['config']=before['config']
        # Only the failed admin component files may change; retain unrelated generated source exactly.
        names=[original_items[i]['fullName'] for i in changed]
        def repair_path(path):
            return any('/flows/'+n+'.flow-meta.xml' in path or
                ('/objects/'+n.split('.')[0]+'/validationRules/'+n.split('.')[-1]+'.validationRule-meta.xml') in path
                for n in names)
        from copy import deepcopy
        for key in ('baseFiles','files'):
            repaired_files={path:source for path,source in package[key].items() if repair_path(path)}
            package[key]=deepcopy(old[key])
            package[key].update(repaired_files)
        if old.get('metadataSpecification'):
            updated_by_id={i['itemId']:i for i in package['metadataSpecification']['metadata']}
            package['metadataSpecification']=deepcopy(old['metadataSpecification'])
            for item in package['metadataSpecification']['metadata']:
                if item['itemId'] in changed:item['config']=updated_by_id[item['itemId']]['config']
        package['components']=deepcopy(old['components'])
        package['testClasses']=deepcopy(old['testClasses'])
        package['sourceHash']=default_pipeline.fingerprint(package)
    plan=ImplementationPlan.model_validate(package['plan'])
    package['evaluationOriginPlanId']=plan.id
    plan_store.save(plan)
    metadata_spec_store.delete(plan.id);change_spec_store.delete(plan.id)
    metadata_spec_store.save_package(package)
    if repair_package:
        from Backend.AI.app.services.layout_selection_service import plan_fingerprint
        old_layout=layout_workflow._states.get(plan.id)
        if old_layout:
            old_layout['planFingerprint']=plan_fingerprint(plan)
        # Component-only repairs do not change field placement; reuse reviewed layout source.
        package['layoutSelections']=repair_package['layoutSelections']
        package['layoutReady']=repair_package['layoutReady']
        package['systemAdministratorFLS']=repair_package.get('systemAdministratorFLS',{})
        package['pageLayouts']=repair_package.get('pageLayouts',{})
        package['sourceHash']=default_pipeline.fingerprint(package)
        metadata_spec_store.save_package(package)
        options={'ready':False}
    else:
        options=layout_workflow.options(plan.id)
    if options['ready']:
        package=default_pipeline.prepare_review(package,plan,layout_workflow.require(plan))
        metadata_spec_store.save_package(package)
    if http_request:
        owner=user(http_request)
        with db() as c:c.execute('INSERT OR REPLACE INTO plans VALUES(?,?,?)',(plan.id,owner['id'],org))
        save_chat(owner['id'],org,plan.id,requirement)
        if activity_title:record_activity(owner['id'],org,plan.id,'generated',activity_title,requirement,'generated')
    response=validate_generated_draft(plan.id)
    # Include layout/FLS preparation and persistence in user-visible plan latency.
    from Backend.AI.app.services.evaluation_service import record_event
    generation_id=package.get('performance',{}).get('generationId')
    if generation_id:
        try:
            record_event('draft_ready', {'generationId':generation_id,
                'totalSeconds':round(perf_counter()-draft_started,3)}, plan.id, generation_id)
        except Exception:
            logging.getLogger(__name__).exception('Draft readiness metrics could not be recorded')
    return response


def revision_package(plan_id):
    package=metadata_spec_store.get_package(plan_id)
    if not package:raise HTTPException(404,'Saved package is unavailable. Load its requirement from chat history and generate it again.')
    if package['targetOrg']!=target_org():raise HTTPException(403,'This package belongs to a different org.')
    if package.get('state') in ('queued','running','pending','unknown','deployed','rejected'):
        raise HTTPException(409,'Check the saved Salesforce operation before changing this plan.')
    return package


@app.post('/api/plans/{plan_id}/revise')
@layout_workflow.locked
def revise_default_plan(plan_id:str,request:RevisionRequest,http_request:Request):
    package=revision_package(plan_id)
    try:return build_default_draft(request.requirement,package['targetOrg'],get_ai_provider(),http_request,'Plan revised — approval required')
    except HTTPException:raise
    except ValueError as error:raise HTTPException(422,planning_error_detail(error)) from error
    except RuntimeError as error:raise HTTPException(502,str(error)) from error


from Backend.AI.app.services.evaluation_service import plan_measurement


@app.post('/api/plans/{plan_id}/repair')
@layout_workflow.locked
@plan_measurement
def repair_default_plan(plan_id:str,request:RepairRequest,http_request:Request):
    from Backend.AI.app.services.plan_revision_service import RepairProvider,repair_context
    package=revision_package(plan_id)
    if request.source_hash is not None and request.source_hash != package['sourceHash']:
        raise HTTPException(409,'Source changed. Reload before repairing.')
    selected = next((c for c in package.get('components',[]) if c.get('fullName') == request.component_name), None)
    flow_config_repair = selected is not None and selected.get('metadataType') == 'Flow'
    if request.component_name and request.source_hash is not None and not flow_config_repair:
        from Backend.AI.app.services.component_source_service import repair_sources
        if request.source_hash != package['sourceHash']:
            raise HTTPException(409,'Source changed. Reload before repairing.')
        try:
            from Backend.AI.app.services.planning_performance import measured_repair
            with measured_repair(get_ai_provider(),plan_id) as measured:
                files=repair_sources(package,request.component_name,request.instruction,measured)
                return save_component_source(plan_id,package,request.component_name,files,request.source_hash)
        except ValueError as error:raise HTTPException(422,str(error)) from error
        except RuntimeError as error:raise HTTPException(502,str(error)) from error
    provider=RepairProvider(get_ai_provider(),repair_context(package,request.component_name))
    try:return build_default_draft(package['requirement'],package['targetOrg'],provider,http_request,'Component repaired — approval required',repair_package=package)
    except HTTPException:raise
    except ValueError as error:raise HTTPException(422,planning_error_detail(error)) from error
    except RuntimeError as error:raise HTTPException(502,str(error)) from error


def save_component_source(plan_id, package, name, files, expected_hash):
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    from Backend.AI.app.services.component_source_service import apply_source_changes
    updated=apply_source_changes(package,name,files,expected_hash,default_pipeline.fingerprint)
    plan=ImplementationPlan.model_validate(updated['plan'])
    plan.status='DRAFT'
    for item in plan.items:item.approval='PENDING'
    plan_store.save(plan)
    metadata_spec_store.save_package(updated)
    return validate_generated_draft(plan_id)


class ComponentSelectionRequest(BaseModel):
    source_hash: str = Field(min_length=64, max_length=64)
    components: list[str] = Field(min_length=1, max_length=500)


@app.post('/api/plans/{plan_id}/selection')
@layout_workflow.locked
def select_plan_components(plan_id: str, request: ComponentSelectionRequest, http_request: Request):
    from copy import deepcopy
    from uuid import uuid4
    from Backend.AI.app.services.component_selection_service import select_components
    from Backend.AI.app.services.layout_selection_service import affected_objects, plan_fingerprint
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    from Backend.AI.app.account_api import user, db
    original = revision_package(plan_id)
    try:
        package = select_components(original, request.components, request.source_hash, default_pipeline.fingerprint)
        new_id = 'PLAN-' + uuid4().hex[:12]
        package['id'] = new_id
        package['plan']['id'] = new_id
        package['plan']['status'] = 'DRAFT'
        for item in package['plan']['items']:
            item['approval'] = 'PENDING'
        if package.get('metadataSpecification'):
            package['metadataSpecification']['planId'] = new_id
        plan = ImplementationPlan.model_validate(package['plan'])
        package['sourceHash'] = default_pipeline.fingerprint(package)
        state = layout_workflow._states.get(plan_id)
        if state:
            state = deepcopy(state)
            affected = affected_objects(plan)
            state['planFingerprint'] = plan_fingerprint(plan)
            state['snapshotId'] = str(uuid4())
            state['objects'] = [o for o in state['objects'] if o['object'] in affected]
            for obj in state['objects']:
                obj['fields'] = affected[obj['object']]['fields']
            state['selected'] = {k: v for k, v in state['selected'].items() if k in affected}
            layout_workflow._states[new_id] = state
        plan_store.save(plan)
        metadata_spec_store.save_package(package)
        options = layout_workflow.options(new_id)
        if options['ready']:
            package = default_pipeline.prepare_review(package, plan, layout_workflow.require(plan))
            metadata_spec_store.save_package(package)
        owner = user(http_request)
        with db() as connection:
            connection.execute('INSERT INTO plans VALUES(?,?,?)', (new_id, owner['id'], package['targetOrg']))
        return validate_generated_draft(new_id)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post('/api/plans/{plan_id}/source')
@layout_workflow.locked
def edit_component_source(plan_id:str,request:SourceEditRequest):
    package=revision_package(plan_id)
    try:return save_component_source(plan_id,package,request.component_name,request.files,request.source_hash)
    except ValueError as error:raise HTTPException(422,str(error)) from error


# SQLite stores the exact package and layout review state, including running jobs.
def persist_workspace_package(package):
    from Backend.AI.app.account_api import current_account,current_org,db
    owner=current_account.get();org=current_org.get()
    if not owner or org!=package.get('targetOrg'):return
    plan_id=package['plan']['id'];plan=plan_store.get(plan_id)
    if not plan:return
    snapshot={'package':package,'plan':plan.model_dump(),'layoutState':layout_workflow._states.get(plan_id)}
    with db() as c:
        if not c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?',(org,owner)).fetchone():
            raise HTTPException(403,'This org is no longer connected to your account.')
        payload=json.dumps(snapshot,sort_keys=True,separators=(',',':'))
        prior=c.execute('SELECT payload FROM workspace_packages WHERE id=? AND user_id=? AND org_id=?',(plan_id,owner,org)).fetchone()
        if not prior or prior['payload']!=payload:
            c.execute('INSERT OR REPLACE INTO workspace_packages VALUES(?,?,?,?)',(plan_id,owner,org,payload))
        if package.get('state') in {'running','pending','unknown'}:
            c.execute('INSERT INTO monitor_jobs VALUES(?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET next_poll=excluded.next_poll', (plan_id,owner,org, time.time()+5))
        else:
            c.execute('DELETE FROM monitor_jobs WHERE plan_id=? AND user_id=? AND org_id=?',(plan_id,owner,org))
    from Backend.AI.app.services.job_notifications import notify
    notify()


def restore_workspace_package(plan_id,owner,org):
    from Backend.AI.app.services.app_database import postgres_enabled
    if postgres_enabled():
        return _restore_workspace_package_locked(plan_id,owner,org,force=True)
    if plan_store.get(plan_id) is not None and metadata_spec_store.get_package(plan_id) is not None:
        return
    return _restore_workspace_package_locked(plan_id,owner,org)


@layout_workflow.locked
def _restore_workspace_package_locked(plan_id,owner,org,force=False):
    if not force and plan_store.get(plan_id) and metadata_spec_store.get_package(plan_id):return
    from Backend.AI.app.account_api import db
    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    with db() as c:row=c.execute('SELECT payload FROM workspace_packages WHERE id=? AND user_id=? AND org_id=?',(plan_id,owner,org)).fetchone()
    if not row:return
    try:
        from copy import deepcopy
        snapshot=json.loads(row['payload']);package=snapshot['package']
        corrected_result = False
        if package.get('state') == 'deployed' and package.get('lastResult', {}).get('result', {}).get('checkOnly') is True:
            package.update(state='unknown', validatedHash=None,
                error='The saved result is validation-only. No real deployment is confirmed.',
                nextAction='Inspect the saved Salesforce job and backend deployment logs before retrying.')
            corrected_result = True
        if package['targetOrg']!=org or package['plan']['id']!=plan_id:raise ValueError('Saved package identity mismatch.')
        default_pipeline.verify_package(package)
        plan=ImplementationPlan.model_validate(snapshot['plan'])
        default_pipeline.assert_plan(package,plan)
        plan_store.save(plan)
        if package.get('state')=='running' and not force:
            package.update(state='unknown',validatedHash=None,error='The backend restarted during submission. Review Salesforce Deployment Status before retrying.',
                nextAction='Inspect the saved job if available; do not submit another deployment until the original outcome is confirmed.')
        if snapshot.get('layoutState'):layout_workflow._states[plan_id]=snapshot['layoutState']
        # Refreshing an unchanged snapshot must not emit new jobs or metrics.
        if corrected_result or (not force and package.get('state') == 'unknown'):
            metadata_spec_store.save_package(package)
        else:
            metadata_spec_store._packages[plan_id] = deepcopy(package)
    except (ValueError,KeyError,TypeError) as error:
        raise HTTPException(409,'Saved package could not be restored safely. Generate a new plan from its saved requirement.') from error


def persist_and_measure_package(package):
    persist_workspace_package(package)
    from Backend.AI.app.services.evaluation_service import safe_observe_package
    safe_observe_package(package)


metadata_spec_store.on_save=persist_and_measure_package


# A single-process development worker follows persisted jobs without an open browser.
# Multiple production workers require a durable queue/lease instead of this thread.
_job_stop = None
_job_thread = None

def start_saved_job_monitor():
    global _job_stop, _job_thread
    from threading import Event, Thread
    from Backend.AI.app.services.saved_job_monitor import monitor_saved_jobs
    _job_stop=Event()
    _job_thread=Thread(target=monitor_saved_jobs,args=(_job_stop,),daemon=True,name='salesforce-job-monitor')
    _job_thread.start()

def stop_saved_job_monitor():
    if _job_stop:_job_stop.set()

from contextlib import asynccontextmanager
@asynccontextmanager
async def workspace_lifespan(app):
    import os
    from Backend.AI.app.services.app_database import postgres_enabled
    external = os.getenv('APP_JOB_MODE', 'inline') == 'external'
    if external and (not postgres_enabled() or not os.getenv('APP_ENCRYPTION_KEY')):
        raise RuntimeError('External jobs require Postgres and a shared APP_ENCRYPTION_KEY.')
    if os.getenv('APP_BACKGROUND_JOBS','false').lower()=='true' and not external:
        raise RuntimeError('Background operations require APP_JOB_MODE=external.')
    if not external:
        start_saved_job_monitor()
    try:yield
    finally:stop_saved_job_monitor()
app.router.lifespan_context=workspace_lifespan


@app.get('/api/plans/{plan_id}/status')
def saved_package_status(plan_id:str):
    # Progress reads must not wait behind a long worker submission lock.
    from Backend.AI.app.account_api import db,current_account,current_org
    with db() as connection:
        row=connection.execute('SELECT payload FROM workspace_packages WHERE id=? AND user_id=? AND org_id=?', (plan_id,current_account.get(),current_org.get())).fetchone()
    package=json.loads(row['payload'])['package'] if row else metadata_spec_store.get_package(plan_id)
    if not package:raise HTTPException(404,'Generated package not found.')
    if package['targetOrg']!=target_org():raise HTTPException(403,'This package belongs to a different org.')
    if package.get('state') in {'queued','running'} and package.get('backgroundJobId') and not package.get('jobId'):
        with db() as connection:
            job=connection.execute('SELECT state,result FROM background_jobs WHERE id=? AND user_id=? AND org_id=?', (package['backgroundJobId'],current_account.get(),current_org.get())).fetchone()
        if job and job['state'] in {'failed','unknown'}:
            detail=json.loads(job['result'] or '{}').get('detail')
            message=detail.get('message') or detail.get('question') or 'Background operation failed.' if isinstance(detail,dict) else str(detail or 'Background operation failed.')
            package.update(state=job['state'],error=message,nextAction='Inspect the saved operation before retrying.')
    return {key:package.get(key) for key in ('state','jobId','operation','sourceHash','validatedHash','approvedHash','error','nextAction','lastResult','errorDetails','operationSeconds','localChecks')}


@app.get('/api/evaluation/summary')
def evaluation_summary(request: Request, org_id: str | None = None):
    from Backend.AI.app.account_api import user, db
    from Backend.AI.app.services.evaluation_service import summary
    account = user(request)
    if org_id:
        with db() as c:
            owned = c.execute('SELECT id FROM orgs WHERE id=? AND user_id=?', (org_id, account['id'])).fetchone()
        if not owned:
            raise HTTPException(404, 'Org not found.')
    return summary(account['id'], org_id)


@app.get('/api/jobs/{job_id}')
def background_job_status(job_id: str):
    from Backend.AI.app.account_api import current_account
    from Backend.AI.app.services.background_jobs import get_owned
    return get_owned(job_id,current_account.get())
