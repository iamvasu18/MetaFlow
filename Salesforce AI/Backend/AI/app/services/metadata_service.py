from Backend.AI.app.services.salesforce_api_client import connected_api
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
import logging
from Backend.AI.app.services.planning_performance import planning_cache, timed_generation
import hashlib
import json
from pathlib import Path
import tempfile
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Backend.AI.app.prompts.prompt_builder import build_metadata_prompt
from Backend.AI.app.providers.base import AIProvider
from Backend.AI.app.services.discovery_service import (
    simple_object_request, discover_object, request_scope, explicit_objects, referenced_objects,
    check_requested_components, check_planned_components,
)

from Backend.AI.app.services.apex_service import (
    ApexAutomationService,
    ApexRequest,
)
from Backend.AI.app.services.flow_preflight_service import (
    FlowPreflightService,
)
from Backend.AI.app.services.lwc_service import (
    LWCAutomationService,
    LWCRequest,
)
from Backend.AI.app.services.metadata_generator import (
    SalesforceMetadataGenerator,
)
from Backend.AI.app.services.planning_service import PlanningService
from Backend.AI.app.services.profile_fls_service import (
    initialize_deployment_project,
)

from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
    validate_metadata_spec,
)
from Backend.AI.app.validators.plan_validator import (
    ImplementationPlan,
)


def _parse_metadata_json(response: str) -> dict:
    """
    Parse raw JSON or JSON wrapped in Markdown code fences.

    Arbitrary prose is not silently accepted.
    """
    if not isinstance(response, str):
        raise ValueError("AI response must be a string.")

    cleaned = response.strip()

    if not cleaned:
        raise ValueError("AI returned an empty response.")

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        preview = cleaned[:500]

        raise ValueError(
            "AI returned invalid metadata JSON. "
            f"Response starts with: {preview!r}. "
            f"JSON error: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "AI metadata response must be a JSON object."
        )

    return parsed


class MetadataService:
    """
    Convert an approved ImplementationPlan into a validated
    MetadataSpecification.

    XML generation and deployment are handled separately.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def generate_specification(
        self,
        plan: ImplementationPlan,
        salesforce_context: dict | None = None,
    ) -> MetadataSpecification:
        if plan.status != "APPROVED":
            raise ValueError(
                "Only APPROVED plans can generate "
                "a metadata specification."
            )

        # Flow-only conversion uses the already validated plan config.
        # It does not require a second AI generation call.
        flow_only = plan.items and all(
            item.metadataType in {"Flow", "PermissionSet"}
            and item.action in {"CREATE", "NO_CHANGE"}
            for item in plan.items
        )

        if flow_only:
            if any(
                item.approval != "APPROVED"
                for item in plan.items
                if item.action == "CREATE"
            ):
                raise ValueError(
                    "All CREATE Flow items must be APPROVED."
                )

            return MetadataSpecification.model_validate(
                {
                    "planId": plan.id,
                    "validationIssues": [],
                    "metadata": [
                        {
                            "itemId": item.id,
                            "action": "CREATE",
                            "metadataType": item.metadataType,
                            "fullName": item.fullName,
                            "label": item.label,
                            "description": item.description,
                            "dependencies": deepcopy(
                                item.dependencies
                            ),
                            "config": deepcopy(item.config),
                        }
                        for item in plan.items
                        if item.action == "CREATE"
                    ],
                }
            )

        if any(item.approval != "APPROVED" for item in plan.items if item.action=="CREATE"):
            raise ValueError("All CREATE items must be APPROVED before metadata conversion.")

        # Reuse complete validated configuration instead of asking AI to rewrite it.
        # Unknown/unsupported schemas retain the existing checked conversion path.
        canonical=[]
        for item in plan.items:
            if item.action != "CREATE":continue
            config=deepcopy(item.config)
            if item.metadataType=="CustomField" and "fieldType" in config:
                from Backend.AI.app.services.salesforce_capability_registry import SalesforceCapabilityRegistry
                config["type"]=SalesforceCapabilityRegistry.normalize_field_type(config.pop("fieldType"))
            canonical.append(dict(itemId=item.id,action=item.action,metadataType=item.metadataType,
                fullName=item.fullName,label=item.label,description=item.description,
                dependencies=deepcopy(item.dependencies),config=config))
        try:
            direct=MetadataSpecification.model_validate(dict(planId=plan.id,metadata=canonical,validationIssues=[]))
        except ValueError:
            direct=None
        if direct is not None:
            return direct

        if salesforce_context is None:
            salesforce_context = {"objects": []}

        if not isinstance(salesforce_context, dict):
            raise ValueError(
                "Salesforce context must be a dictionary."
            )

        final_prompt = build_metadata_prompt(
            implementation_plan=plan.model_dump(),
            salesforce_context=salesforce_context,
        )

        ai_response = self.provider.generate(
            system_prompt=(
                "You are a Salesforce metadata "
                "specification assistant. "
                "Return only valid JSON conforming "
                "to metadata-spec-v001."
            ),
            user_prompt=final_prompt,
        )

        specification_data = _parse_metadata_json(ai_response)
        validation = validate_metadata_spec(specification_data)

        if not validation.valid:
            raise ValueError(
                "AI generated an invalid metadata specification: "
                + "; ".join(validation.errors)
            )

        specification = MetadataSpecification.model_validate(
            specification_data
        )

        if specification.planId != plan.id:
            raise ValueError(
                "Metadata specification planId "
                "does not match the implementation plan."
            )

        from Backend.AI.app.validators.flow_validator import (
            validate_flow_spec_matches_plan,
        )

        validate_flow_spec_matches_plan(plan, specification)

        return specification


def load_metadata_generation_context(
    plan,
    salesforce_service,
) -> dict:
    """
    Discover existing plan targets while keeping planned new
    components separate from verified org metadata.
    """
    flow_only = plan.items and all(
        item.metadataType == "Flow"
        and item.action in {"CREATE", "NO_CHANGE"}
        for item in plan.items
    )

    if flow_only:
        return {"objects": []}

    creates = [
        item for item in plan.items
        if item.action == "CREATE"
    ]

    new_objects = {
        item.fullName
        for item in creates
        if item.metadataType == "CustomObject"
    }

    names = set()

    for item in creates:
        if item.metadataType in {
            "CustomField",
            "ValidationRule",
        }:
            names.add(item.fullName.split(".", 1)[0])

        if item.metadataType == "CustomField":
            targets = item.config.get("referenceTo", [])

            names.update(
                [targets]
                if isinstance(targets, str)
                else targets
            )

            value = item.config.get("summaryForeignKey")

            if isinstance(value, str) and "." in value:
                names.add(value.split(".", 1)[0])

        if item.metadataType == "Flow":
            from Backend.AI.app.validators.flow_validator import (
                flow_objects,
                validate_flow,
            )

            names.update(
                flow_objects(
                    validate_flow(
                        item.fullName,
                        item.label,
                        item.config,
                    )
                )
            )

    existing = sorted(names - new_objects)

    context = (
        salesforce_service.get_context(existing)
        if existing
        else {"objects": []}
    )

    return dict(
        context,
        plannedComponents=[
            {
                "itemId": item.id,
                "metadataType": item.metadataType,
                "fullName": item.fullName,
                "dependencies": item.dependencies,
                "config": deepcopy(item.config),
            }
            for item in creates
            if item.metadataType in {
                "CustomObject",
                "CustomField",
            }
        ],
    )


SUPPORTED = {
    "PermissionSet",
    "CustomObject",
    "CustomField",
    "ValidationRule",
    "Flow",
    "ApexClass",
    "ApexTrigger",
    "LightningComponentBundle",
}

GUIDANCE = """PermissionSet CREATE is supported with label and strict config objectPermissions, fieldPermissions, classAccesses, userPermissions and optional license. Never add Profile edits or automatic user assignments.
LWC getObjectInfo/getPicklistValues are wire adapters: use @wire, never imperative calls.
Respect explicitly requested field types. A Number field populated by a Flow
is not a Salesforce Formula field. For independent Flow calculations use contractVersion=2
and config.expressions [{name,dataType,expression,scale}], never formulas.sourceField.
config.formulas is exclusively for verified existing calculated Salesforce fields.
For inclusive date differences use a Number expression with the two date references
and +1, guarded for blank dates. Use a Boolean expression/Decision for creation
or changes to the requested dates; do not replace that condition with every update. Choose before-save Assignment for same-record updates.
Fields/objects created by this plan are dependencies, not missing existing metadata.
Declare dependency item IDs for every same-plan reference. Never change a user's Number
field to Formula to satisfy validation. CREATE CustomObject supports enableReports=true.
Status-transition validation must use PRIORVALUE for the previous value, not current value.
Preserving unrelated metadata is not a request to alter sharing/access.
The default workflow includes real Apex and LWC generators.
Select the needed components from the requirement and verified org context.
For a Lightning UI add LightningComponentBundle with a lower-camel-case fullName
and config {"isExposed":true,"targets":["lightning__AppPage"]}, choosing actual
requested targets. For Apex add ApexClass with config.apexKind, and ApexTrigger
with config.sobject and config.events when needed. Group related Apex classes,
triggers and tests into one package. Source bodies may be omitted at planning:
the dedicated generator writes complete source and tests before user review.
Declare dependencies using item IDs. Prefer Flow or declarative metadata when
appropriate; do not force every requirement into Apex. Do not omit companion
components. This execution path supports CREATE and NO_CHANGE only. Existing
components must not be relabeled CREATE to bypass this restriction. UPDATE or
unsupported dependencies must be reported honestly. LWC currently uses LDS/UI
API without Apex imports. Do not pretend an Apex-connected LWC is supported.
Return the existing complete ImplementationPlan JSON contract, not a router
classification, not source code, and never set user approval to APPROVED.
"""


class DefaultGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(
        min_length=1,
        max_length=20000,
    )

    target_org: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.@+\-]{0,199}$",
    )

    @field_validator("requirement")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Requirement cannot be blank.")

        return value.strip()


class PlanningProvider:
    """
    Add default-workflow guidance without duplicating raw org
    metadata already selected by PlanningService.
    """

    def __init__(self, provider, context):
        self.provider = provider
        self.context = context

    def generate(self, system_prompt, user_prompt):
        # PlanningService already selects and projects object metadata.
        # Appending the full raw context would bypass that reduction.
        # Full discovery metadata remains available to backend validators.
        supplemental = {
            "permissionSetCapabilities": self.context.get("permissionSetCapabilities"),
            "focusedObjectRequest": self.context.get("focusedObjectRequest"),
            "discoveryScope": self.context.get("discoveryScope"),
            "existingComponents": {},
            "inventoryPolicy": "Whole-org inventories are omitted from prompts. Generated identities are checked against the full live inventory by the backend; omission never proves absence.",
            "validationRuleDiscovery": self.context.get(
                "validationRuleDiscovery",
                {},
            ),
        }

        return self.provider.generate(
            system_prompt=system_prompt + "\n" + GUIDANCE + "\nWhen a User answer follows a clarification, follow that answer for the conflicted component identity and preserve unrelated requirements. If focusedObjectRequest is provided, create exactly that object API name and label, preserve enableReports, and do not add fields, rules or other components.",
            user_prompt=(
                user_prompt
                + "\nVERIFIED_DEFAULT_CONTEXT:\n"
                + json.dumps(
                    supplemental,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
            ),
        )


class DefaultMetadataPipeline(ApexAutomationService):
    """
    Integrate the existing metadata, Apex and LWC generators.

    Local preview approval is isolated from saved user approval.
    Deployment uses the exact reviewed source package.
    """

    def __init__(
        self,
        *args,
        lwc_service=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.lwc_service = lwc_service or LWCAutomationService(
            self.project_root,
            tooling_root=self.tooling_root,
        )

    def discover(self, request):
        from Backend.AI.app.account_api import current_account
        started = perf_counter()
        owner = current_account.get()
        key = (owner, request.target_org, self.version(), ("requirement", request.requirement))
        metadata = self.metadata_factory(request.target_org)
        metadata._cache_owner = owner
        api=connected_api(metadata)
        focused=simple_object_request(request.requirement)
        cached, epoch = planning_cache.get(key) if owner else (None, None)
        if cached is not None and not focused:
            logging.getLogger(__name__).warning(
                "Planning discovery seconds=%.3f cache=hit", perf_counter() - started
            )
            return metadata, cached


        if focused:
            context=discover_object(self,request.target_org,focused,api=connected_api(metadata))
            if owner:planning_cache.put(key,context,epoch)
            logging.getLogger(__name__).warning('Planning discovery seconds=%.3f cache=miss scope=exact-object',perf_counter()-started)
            return metadata,context

        scope=request_scope(request.requirement)
        catalog=metadata.list_objects()
        from Backend.AI.app.services.discovery_service import check_object_dependencies
        check_object_dependencies(request.requirement,catalog)
        objects=explicit_objects(request.requirement,catalog)
        if not objects:
            objects=metadata.find_relevant_objects(request.requirement)

        if len(objects) > 10:
            raise ValueError(
                "Requirement spans more than 10 objects; "
                "narrow the scope."
            )

        object_key = (owner, request.target_org, self.version(), ("objects", tuple(objects)))
        context, object_epoch = planning_cache.get(object_key) if owner else (None, None)
        if context is None:
            context = metadata.get_context(objects) if objects else {"objects": []}
            if owner:
                planning_cache.put(object_key, context, object_epoch)

        # Expand only explicitly referenced lookup relationships, keeping original metadata.
        for _ in range(10):
            known={obj['name'] for obj in context.get('objects',[])}
            related=referenced_objects(request.requirement,context)-known
            if not related:break
            if len(known|related)>10:raise ValueError('Referenced object dependencies exceed the supported scope; split the requirement.')
            extra=metadata.get_context(sorted(related))
            context['objects'].extend(extra.get('objects',[]))
        objects=[obj['name'] for obj in context.get('objects',[])]

        from Backend.AI.app.services.apex_org_context import (
            ApexOrgContext,
        )

        discovery = self.rule_discovery or (
            (lambda context, org, version: api.enrich_validation_rules(context))
            if api else ApexOrgContext(self.cli).enrich
        )

        rule_key = (owner, request.target_org, self.version(), ('rules', tuple(objects)))
        def enriched_context():
            if not scope['requiresRules']:
                skipped=deepcopy(context)
                skipped['validationRuleDiscovery']={'status':'not-requested','reason':'Schema-only request; existing business rules were not inspected.'}
                return skipped
            enriched, rule_epoch = planning_cache.get(rule_key) if owner else (None, None)
            if enriched is None:
                enriched = discovery(context, request.target_org, self.version())
                if owner:
                    planning_cache.put(rule_key, enriched, rule_epoch)
            return enriched

        def read_inventory(kind):
            records = api.list_components(kind) if api else self.cli([
                "org", "list", "metadata", "--metadata-type", kind,
                "--target-org", request.target_org,
            ]).get("result")
            if isinstance(records, dict):
                records = [records]
            if not isinstance(records, list):
                raise ValueError("Invalid org component discovery response.")
            return kind, [row["fullName"] for row in records
                          if isinstance(row, dict) and row.get("fullName")]

        kinds=scope['inventoryKinds']
        inventory_key = (owner, request.target_org, self.version(), ('component-inventory',kinds))
        inventory, inventory_epoch = planning_cache.get(inventory_key) if owner else (None, None)
        with ThreadPoolExecutor(max_workers=max(1,len(kinds)+1)) as executor:
            rules_future = executor.submit(enriched_context)
            if inventory is None:
                inventory = dict(executor.map(read_inventory,kinds))
                if owner:planning_cache.put(inventory_key,inventory,inventory_epoch)
            context = rules_future.result()
        context['discoveryScope']={**scope,'inspectedObjectNames':objects,
            'uninspectedComponentTypes':[k for k in ('ApexClass','ApexTrigger','LightningComponentBundle','Flow') if k not in kinds]}

        inventory['CustomObject']=[obj['name'] for obj in catalog]
        inventory['CustomField']=[obj['name']+'.'+field['name'] for obj in context.get('objects',[])
            for field in obj.get('fields',[]) if field.get('name')]
        inventory['ValidationRule']=[rule['fullName'] for obj in context.get('objects',[])
            for rule in obj.get('validationRules',[]) if rule.get('fullName')]
        if 'PermissionSet' in kinds and api:
            permission_description = api.describe_object('PermissionSet')
            context['permissionSetCapabilities'] = {'systemPermissions': sorted(
                field['name'][len('Permissions'):] for field in permission_description['fields']
                if field.get('type') == 'boolean' and field.get('name','').startswith('Permissions'))}
        context["existingComponents"] = inventory
        context["objectCatalog"] = [{"name": obj["name"], "label": obj.get("label")} for obj in catalog if obj.get("name")]

        if owner:
            planning_cache.put(key, context, epoch)
        logging.getLogger(__name__).warning(
            "Planning discovery seconds=%.3f cache=miss", perf_counter() - started
        )
        return metadata, context

    @staticmethod
    def preview(plan, items):
        # Existing generators require an approved input for generation.
        # This isolated copy is never saved as user approval.
        preview_plan = plan.model_copy(deep=True)
        preview_plan.items = deepcopy(items)
        preview_plan.status = "APPROVED"

        for item in preview_plan.items:
            item.approval = "APPROVED"

        return preview_plan

    @timed_generation
    def generate(self, request, provider):
        metadata, context = self.discover(request)
        api=connected_api(metadata)
        check_requested_components(request.requirement, context)

        planner = PlanningService(
            PlanningProvider(provider, context),
            metadata_service=metadata,
        )

        plan = planner.generate_plan(
            request.requirement,
            salesforce_context=context,
        )

        missing_inventory={i.metadataType for i in plan.items if i.action!='NO_CHANGE' and
            i.metadataType in {'ApexClass','ApexTrigger','LightningComponentBundle','Flow','PermissionSet'} and
            i.metadataType not in context.get('existingComponents',{})}
        for kind in sorted(missing_inventory):
            rows=api.list_components(kind) if api else self.cli(['org','list','metadata','--metadata-type',kind,'--target-org',request.target_org]).get('result')
            if isinstance(rows,dict):rows=[rows]
            if not isinstance(rows,list):raise ValueError('Required generated-component discovery did not complete.')
            context.setdefault('existingComponents',{})[kind]=[r['fullName'] for r in rows if isinstance(r,dict) and r.get('fullName')]
        if any(i.metadataType in {'ApexClass','ApexTrigger','Flow','ValidationRule'} for i in plan.items) and context.get('validationRuleDiscovery',{}).get('status')=='not-requested':
            from Backend.AI.app.services.apex_org_context import ApexOrgContext
            context=self.rule_discovery(context,request.target_org,self.version()) if self.rule_discovery else (api.enrich_validation_rules(context) if api else ApexOrgContext(self.cli).enrich(context,request.target_org,self.version()))

        check_planned_components(plan,request.requirement,context)

        if context.get('focusedObjectRequest'):
            expected=context['focusedObjectRequest']['fullName']
            active_items=[i for i in plan.items if i.action!='NO_CHANGE']
            if len(active_items)!=1 or active_items[0].action!='CREATE' or active_items[0].metadataType!='CustomObject' or active_items[0].fullName!=expected:
                raise ValueError('Object-only generation changed the requested scope or API name. No package was saved.')
            if context['focusedObjectRequest']['enableReports'] and not active_items[0].config.get('enableReports'):
                raise ValueError('The generated object omitted requested reporting support. No package was saved.')

        plan.id = "PLAN-" + uuid4().hex[:12]
        plan.status = "DRAFT"

        for item in plan.items:
            item.approval = "PENDING"

        active = [
            item
            for item in plan.items
            if item.action != "NO_CHANGE"
        ]

        if not active:
            raise ValueError(
                "No deployable changes were identified."
            )

        for item in active:
            if item.metadataType not in SUPPORTED:
                raise ValueError(
                    "Generator not connected for "
                    + item.metadataType
                    + "."
                )

            if item.action != "CREATE":
                raise ValueError(
                    item.fullName
                    + ": this unified path supports new "
                    "components only; existing UPDATE "
                    "endpoints remain available."
                )

            existing = context["existingComponents"].get(
                item.metadataType,
                [],
            )

            if item.fullName in existing:
                raise ValueError(
                    item.fullName
                    + " already exists. An UPDATE cannot "
                    "be silently treated as CREATE."
                )

        for permission in active:
            if permission.metadataType == 'PermissionSet':
                from Backend.AI.app.services.permission_set_service import preflight_permission_set
                preflight_permission_set(permission.fullName, permission.label, permission.config, api, plan.model_dump(), context)

        files = {}
        components = {}
        tests = []
        warnings = []
        admin_spec = None

        def merge(package):
            for path, body in package["files"].items():
                if path in files:
                    raise ValueError(
                        "Duplicate generated file: " + path
                    )

                files[path] = body

            for component in package["components"]:
                key = (
                    component["metadataType"],
                    component["fullName"],
                )

                components[key] = component

            tests.extend(package.get("testClasses", []))

            warnings.extend(
                package.get("localChecks", {}).get(
                    "warnings",
                    [],
                )
            )

        apex = [
            item
            for item in active
            if item.metadataType in {
                "ApexClass",
                "ApexTrigger",
            }
        ]

        if apex:
            primary = next(
                (
                    item
                    for item in apex
                    if item.metadataType == "ApexClass"
                    and item.config.get("apexKind") != "Test"
                ),
                None,
            )

            if primary is None:
                raise ValueError(
                    "Apex package needs a planned "
                    "production class/trigger handler."
                )

            package = super().generate(
                ApexRequest(
                    class_name=primary.fullName,
                    requirement=(
                        request.requirement
                        + "\nImplement every planned Apex "
                        "component exactly:\n"
                        + json.dumps(
                            [
                                item.model_dump()
                                for item in apex
                            ]
                        )
                    ),
                    target_org=request.target_org,
                    objects=[
                        obj['name']
                        for obj in context.get('objects', [])
                        if obj.get('name')
                    ],
                ),
                provider,
            )

            generated_keys = {
                (
                    item["metadataType"],
                    item["fullName"],
                )
                for item in package["components"]
            }

            if any(
                (item.metadataType, item.fullName)
                not in generated_keys
                for item in apex
            ):
                raise ValueError(
                    "Apex generator omitted a planned component."
                )

            merge(package)

        for item in active:
            if item.metadataType != "LightningComponentBundle":
                continue

            depends_on_apex = any(
                plan_item.metadataType
                in {"ApexClass", "ApexTrigger"}
                and plan_item.id in item.dependencies
                for plan_item in plan.items
            )

            if depends_on_apex:
                raise ValueError(
                    "Apex-connected LWC generation is not "
                    "supported by the existing LDS-only "
                    "LWC service."
                )

            package = self.lwc_service.generate(
                LWCRequest(
                    component_name=item.fullName,
                    requirement=(
                        request.requirement
                        + "\nImplement this planned component:\n"
                        + json.dumps(item.model_dump())
                    ),
                    target_org=request.target_org,
                    targets=(item.config or {}).get(
                        "targets",
                        ["lightning__AppPage"],
                    ),
                ),
                provider,
            )

            package["components"] = [
                {
                    "metadataType": "LightningComponentBundle",
                    "fullName": item.fullName,
                }
            ]

            merge(package)

        admin = [
            item
            for item in active
            if item.metadataType
            not in {
                "ApexClass",
                "ApexTrigger",
                "LightningComponentBundle",
            }
        ]

        if admin:
            preview_plan = self.preview(plan, admin)

            spec = MetadataService(
                provider
            ).generate_specification(
                preview_plan,
                salesforce_context=context,
            )

            admin_spec = spec

            if spec.validationIssues:
                raise ValueError(
                    "Metadata specification has unresolved "
                    "validation issues."
                )

            expected = {
                (item.metadataType, item.fullName)
                for item in admin
            }

            actual = {
                (item.metadataType, item.fullName)
                for item in spec.metadata
                if item.action == "CREATE"
            }

            if expected != actual:
                raise ValueError(
                    "Metadata generation changed the "
                    "planned component set."
                )

            with tempfile.TemporaryDirectory(
                prefix="implementation-preview-",
                ignore_cleanup_errors=True,
            ) as staging:
                root = Path(staging)

                initialize_deployment_project(
                    self.project_root,
                    root,
                )

                SalesforceMetadataGenerator(
                    staging
                ).generate_from_specification(spec)

                package = {
                    "files": {
                        path.relative_to(root).as_posix():
                        path.read_text(encoding="utf-8")
                        for path in (
                            root / "force-app"
                        ).rglob("*")
                        if path.is_file()
                    },
                    "components": [
                        {
                            "metadataType": item.metadataType,
                            "fullName": item.fullName,
                        }
                        for item in admin
                    ],
                }

                if not package["files"]:
                    raise ValueError(
                        "Metadata generator produced no files."
                    )

                merge(package)

        # Add generated test/helper classes to the review plan.
        planned = {
            (item.metadataType, item.fullName)
            for item in active
        }

        from Backend.AI.app.validators.plan_validator import (
            PlanItem,
        )

        for key in components:
            if key not in planned:
                plan.items.append(
                    PlanItem(
                        id="GENERATED-" + uuid4().hex[:12],
                        action="CREATE",
                        metadataType=key[0],
                        fullName=key[1],
                        config={
                            "apexKind": (
                                "Test"
                                if key[1] in tests
                                else "Standard"
                            )
                        },
                        approval="PENDING",
                    )
                )

        package = {
            "id": str(uuid4()),
            "componentName": plan.summary,
            "targetOrg": request.target_org,
            "requirement": request.requirement,
            "plan": plan.model_dump(),
            "baseFiles": deepcopy(files),
            "metadataSpecification": (
                admin_spec.model_dump()
                if admin_spec
                else None
            ),
            "apiVersion": self.version(),
            "files": files,
            "components": list(components.values()),
            "testClasses": sorted(set(tests)),
            "sourceHash": "",
            "state": "generated",
            "operation": None,
            "validationRuleDiscovery": context.get(
                "validationRuleDiscovery",
                {},
            ),
            "layoutReady": False,
            "layoutSelections": {},
            "localChecks": {
                "valid": True,
                "warnings": warnings,
                "compilation": (
                    "Salesforce validation runs "
                    "before deployment."
                ),
            },
        }

        package["sourceHash"] = self.fingerprint(package)

        return package

    @staticmethod
    def fingerprint(bundle):
        keys = (
            "plan",
            "files",
            "targetOrg",
            "apiVersion",
            "components",
            "testClasses",
            "metadataSpecification",
            "layoutSelections",
            "baseFiles",
        )

        serialized = json.dumps(
            {key: bundle[key] for key in keys},
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode()
        ).hexdigest()

    @classmethod
    def verify_package(cls, bundle):
        digest = cls.fingerprint(bundle)

        if digest != bundle["sourceHash"]:
            raise ValueError(
                "Saved plan/source fingerprint changed. "
                "Generate and review again."
            )

        from Backend.AI.app.services.metadata_safety import source_relative_path, validate_component_name
        for inventory in (bundle["files"], bundle.get("baseFiles", {})):
            for path in inventory:
                source_relative_path(path)
        for item in bundle["components"]:
            validate_component_name(item["metadataType"], item["fullName"])

    def check_tests(self, bundle, payload):
        has_apex = any(
            item["metadataType"]
            in {"ApexClass", "ApexTrigger"}
            for item in bundle["components"]
        )

        if has_apex:
            ApexAutomationService.require_test_execution(
                payload
            )

    def ensure_new(self,bundle):
        from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
        metadata=owned_metadata_api(bundle['targetOrg'],bundle['apiVersion'])
        if not metadata:return super().ensure_new(bundle)
        api=metadata.api
        kinds={item['metadataType'] for item in bundle['components']}
        context={'objects':[],'existingComponents':{},'objectCatalog':[]}
        if kinds & {'CustomObject','CustomField','ValidationRule'}:
            context['objectCatalog']=api.list_objects()
            existing={o.get('name') for o in context['objectCatalog']}
            parents={i['fullName'].split('.')[0] for i in bundle['components'] if i['metadataType'] in {'CustomField','ValidationRule'}} & existing
            context['objects']=[api.describe_object(name) for name in sorted(parents)]
            if 'ValidationRule' in kinds:context=api.enrich_validation_rules(context)
        for kind in kinds & {'ApexClass','ApexTrigger','Flow','LightningComponentBundle','PermissionSet'}:
            context['existingComponents'][kind]=[r['fullName'] for r in api.list_components(kind)]
        check_planned_components(bundle['plan'],bundle.get('requirement',''),context)

    def report(self,bundle):
        from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
        api=owned_metadata_api(bundle['targetOrg'],bundle['apiVersion'])
        return api.report(bundle.get('jobId')) if api else super().report(bundle)

    @staticmethod
    def assert_plan(bundle, plan):
        current = plan.model_dump()
        current["status"] = "DRAFT"

        for item in current["items"]:
            item["approval"] = "PENDING"

        if current != bundle["plan"]:
            raise ValueError(
                "Plan changed after source generation. "
                "Generate a new plan."
            )

    def prepare_review(self, bundle, plan, selections):
        """
        Freeze output from the existing FLS and layout services
        before user approval.
        """
        self.verify_package(bundle)
        self.assert_plan(bundle, plan)

        from Backend.AI.app.services.profile_fls_service import (
            SystemAdministratorFLSService,
            validate_create_specification,
        )
        from Backend.AI.app.services.page_layout_service import (
            PageLayoutService,
        )

        updated = deepcopy(bundle)

        with tempfile.TemporaryDirectory(
            prefix="default-review-",
            ignore_cleanup_errors=True,
        ) as directory:
            root = Path(directory)

            initialize_deployment_project(
                self.project_root,
                root,
            )

            for path, body in bundle["baseFiles"].items():
                from Backend.AI.app.services.metadata_safety import safe_source_target
                target = safe_source_target(root, path)

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                target.write_text(
                    body,
                    encoding="utf-8",
                )

            admin = [
                item
                for item in plan.items
                if item.action == "CREATE"
                and item.metadataType
                not in {
                    "ApexClass",
                    "ApexTrigger",
                    "LightningComponentBundle",
                }
            ]

            spec = (
                MetadataSpecification.model_validate(
                    bundle["metadataSpecification"]
                )
                if bundle["metadataSpecification"]
                else None
            )

            updated["files"] = deepcopy(
                bundle["baseFiles"]
            )

            if spec:
                validate_create_specification(
                    self.preview(plan, admin),
                    spec,
                )

                fls = SystemAdministratorFLSService(
                    root
                ).generate(spec)

                layouts = PageLayoutService(
                    root,
                    bundle["targetOrg"],
                ).generate(
                    spec,
                    selections=selections,
                )

                generated_files = (
                    fls["generatedFiles"]
                    + layouts["generatedFiles"]
                )

                for path in generated_files:
                    updated["files"][
                        Path(path).as_posix()
                    ] = (root / path).read_text(
                        encoding="utf-8"
                    )

                updated["systemAdministratorFLS"] = fls
                updated["pageLayouts"] = layouts

            else:
                updated["systemAdministratorFLS"] = {
                    "generatedFiles": [],
                    "fieldPermissions": [],
                }

                updated["pageLayouts"] = {
                    "generatedFiles": [],
                    "layouts": [],
                }

        updated["layoutSelections"] = deepcopy(
            selections
        )
        updated["layoutReady"] = True
        updated["sourceHash"] = self.fingerprint(updated)
        updated.pop("approvedHash", None)

        return updated

    def deploy(self, bundle, dry_run=True):
        self.verify_package(bundle)

        if (
            not bundle.get("layoutReady")
            or bundle.get("approvedHash")
            != bundle["sourceHash"]
        ):
            raise ValueError(
                "Review layouts and approve the exact "
                "generated source first."
            )

        phase=perf_counter()
        self.ensure_new(bundle)
        # Validate the reviewed XML, including manually edited permissions, against current org facts.
        from Backend.AI.app.services.permission_set_service import source_config, preflight_permission_set
        from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
        permission_transport = owned_metadata_api(bundle['targetOrg'], bundle['apiVersion'])
        for component in bundle['components']:
            if component['metadataType'] == 'PermissionSet':
                from Backend.AI.app.services.metadata_safety import component_path
                label, config = source_config(bundle['files'][component_path('PermissionSet',component['fullName']).as_posix()])
                preflight_permission_set(component['fullName'], label, config.model_dump(), permission_transport.api if permission_transport else None, bundle['plan'])

        logging.getLogger(__name__).warning('Salesforce operation=%s phase=existence-check seconds=%.3f', 'validate' if dry_run else 'deploy',perf_counter()-phase)

        plan = ImplementationPlan.model_validate(
            bundle["plan"]
        )
        plan.status = "APPROVED"

        for item in plan.items:
            item.approval = "APPROVED"

        phase=perf_counter()
        FlowPreflightService(
            bundle["targetOrg"]
        ).validate(plan)
        logging.getLogger(__name__).warning('Salesforce operation=%s phase=flow-preflight seconds=%.3f', 'validate' if dry_run else 'deploy',perf_counter()-phase)

        # Windows CLI processes can retain folder handles briefly.
        # Cleanup must not replace a returned Salesforce result.
        with tempfile.TemporaryDirectory(
            prefix="default-deploy-",
            ignore_cleanup_errors=True,
        ) as directory:
            root = Path(directory)

            initialize_deployment_project(
                self.project_root,
                root,
            )

            project_file = root / "sfdx-project.json"

            project = json.loads(
                project_file.read_text(
                    encoding="utf-8"
                )
            )

            project["sourceApiVersion"] = bundle["apiVersion"]

            project_file.write_text(
                json.dumps(project),
                encoding="utf-8",
            )

            for path, body in bundle["files"].items():
                from Backend.AI.app.services.metadata_safety import safe_source_target
                target = safe_source_target(root, path)

                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                target.write_text(
                    body,
                    encoding="utf-8",
                )

            if bundle["metadataSpecification"]:
                reviewed_plan = (
                    ImplementationPlan.model_validate(
                        bundle["plan"]
                    )
                )

                phase=perf_counter()
                refreshed = self.prepare_review(
                    bundle,
                    reviewed_plan,
                    bundle["layoutSelections"],
                )

                logging.getLogger(__name__).warning('Salesforce operation=%s phase=layout-review seconds=%.3f', 'validate' if dry_run else 'deploy',perf_counter()-phase)
                if refreshed["files"] != bundle["files"]:
                    raise ValueError(
                        "FLS/page layout output changed "
                        "after review. Create a new plan."
                    )

            args = [
                "project",
                "deploy",
                "start",
                "--source-dir",
                str(root / "force-app/main/default"),
                "--target-org",
                bundle["targetOrg"],
                "--async",
            ]

            if bundle["testClasses"]:
                args.extend(
                    [
                        "--test-level",
                        "RunSpecifiedTests",
                    ]
                )

                for name in bundle["testClasses"]:
                    args.extend(["--tests", name])

            if dry_run:
                args.append("--dry-run")

            phase=perf_counter()
            from Backend.AI.app.services.salesforce_metadata_api import owned_metadata_api
            api=owned_metadata_api(bundle['targetOrg'],bundle['apiVersion'])
            payload = api.deploy(bundle,check_only=dry_run) if api else self.cli(args, root)
            logging.getLogger(__name__).warning('Salesforce operation=%s phase=submit seconds=%.3f', 'validate' if dry_run else 'deploy',perf_counter()-phase)
            details = payload.get('result', {})
            if isinstance(details, dict) and details.get('id') and details.get('done') is None and details.get('status') not in {'Succeeded', 'Failed', 'Canceled'}:
                details.update(done=False, status='Pending')

            try:
                self.check_tests(bundle, payload)
            except ValueError as exc:
                if not dry_run:
                    raise RuntimeError(
                        "Deployment test outcome "
                        "needs inspection."
                    ) from exc

                raise

            return payload
