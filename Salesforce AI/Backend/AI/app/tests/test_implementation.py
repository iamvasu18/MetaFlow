import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient as RawTestClient
from uuid import uuid4


@pytest.fixture(autouse=True)
def authenticated_owner(monkeypatch):
    from Backend.AI.app import account_api as accounts
    monkeypatch.setenv("APP_PUBLIC_URL", "http://testserver")
    # This module exercises the mocked CLI adapter; owned API transport is
    # independently covered in test_metadata_api_transport.
    monkeypatch.setattr("Backend.AI.app.services.salesforce_metadata_api.owned_metadata_api", lambda *args: None)
    owner = "test-" + uuid4().hex
    with accounts.db() as db:
        db.execute("INSERT INTO users VALUES(?,?,?,?,?)", (owner, owner+"@test", "Test", "salt", "hash"))
        db.execute("INSERT INTO sessions VALUES(?,?,?)", (accounts.digest(owner), owner, accounts.time.time()+1000))
        db.execute("INSERT INTO orgs VALUES(?,?,?,?,?,?)", ("AIOrg", owner, "Test org", "Sandbox", "test@org", "https://example.salesforce.com"))
    account_token = accounts.current_account.set(owner)
    org_token = accounts.current_org.set("AIOrg")
    try:
        yield
    finally:
        accounts.current_account.reset(account_token)
        accounts.current_org.reset(org_token)
        with accounts.db() as db:
            db.execute("DELETE FROM orgs WHERE user_id=?", (owner,))


def TestClient(app):
    from Backend.AI.app import main, account_api as accounts
    owner = accounts.current_account.get()
    with accounts.db() as db:
        for plan in main.plan_store._plans.values():
            db.execute("INSERT OR REPLACE INTO plans VALUES(?,?,?)", (plan.id, owner, "AIOrg"))
    client = RawTestClient(app)
    client.cookies.set("app_session", owner)
    return client

from Backend.AI.app.services.metadata_service import (
    DefaultMetadataPipeline as ImplementationService,
    DefaultGenerationRequest as ImplementationRequest,
)
from Backend.AI.app.tests.test_apex_enhanced import (
    SOURCE,
    CONTEXT,
    success,
)


PLAN = {
    "id": "PLAN-1",
    "requirementId": "REQ-1",
    "summary": "Search Contacts",
    "status": "DRAFT",
    "items": [
        {
            "id": "APEX-1",
            "action": "CREATE",
            "metadataType": "ApexClass",
            "fullName": "ContactSearchService",
            "config": {"apexKind": "Controller"},
            "approval": "PENDING",
        }
    ],
}


@pytest.fixture
def service(tmp_path):
    (tmp_path / "sfdx-project.json").write_text(
        '{"sourceApiVersion":"67.0"}'
    )

    metadata = Mock()
    metadata.list_objects.return_value = [{"name": "Contact", "label": "Contact"}]
    metadata.find_relevant_objects.return_value = ["Contact"]
    metadata.get_context.return_value = deepcopy(CONTEXT)
    metadata.get_flow_dependency_context.return_value = {}

    value = ImplementationService(
        tmp_path,
        metadata_factory=lambda org: metadata,
        rule_discovery=lambda context, org, version: deepcopy(context),
        lwc_service=Mock(),
    )

    value.cli = Mock(return_value={"result": []})
    return value


def generate(service, plan=PLAN):
    provider = Mock()
    provider.generate.side_effect = [
        json.dumps(plan),
        json.dumps(SOURCE),
    ]

    package = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement="Build a Contact search Apex service"
        ),
        provider,
    )

    return package, provider


def test_general_requirement_plans_then_generates_without_user_approval(
    service,
):
    package, provider = generate(service)

    assert len(package["files"]) == 4
    assert package["testClasses"] == ["ContactSearchServiceTest"]
    assert package["plan"]["status"] == "DRAFT"
    assert all(
        item["approval"] == "PENDING"
        for item in package["plan"]["items"]
    )
    assert package["plan"]["items"][-1]["fullName"] == (
        "ContactSearchServiceTest"
    )

    first = provider.generate.call_args_list[0].kwargs
    assert "VERIFIED_DEFAULT_CONTEXT" in first["user_prompt"]
    assert "default workflow" in first["system_prompt"]
    assert service.cli.call_count == 1
    assert "ApexClass" in service.cli.call_args.args[0]


def test_lwc_selected_by_existing_planner(service):
    plan = deepcopy(PLAN)
    plan["items"] = [
        {
            "id": "UI-1",
            "action": "CREATE",
            "metadataType": "LightningComponentBundle",
            "fullName": "contactSearch",
            "config": {"targets": ["lightning__AppPage"]},
        }
    ]

    service.lwc_service.generate.return_value = {
        "files": {
            "force-app/main/default/lwc/contactSearch/contactSearch.js":
                "export default class ContactSearch {}"
        },
        "localChecks": {"warnings": []},
    }

    provider = Mock()
    provider.generate.return_value = json.dumps(plan)

    result = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement="Show a Contact search UI"
        ),
        provider,
    )

    assert result["components"] == [
        {
            "metadataType": "LightningComponentBundle",
            "fullName": "contactSearch",
        }
    ]

    assert (
        service.lwc_service.generate.call_args.args[0].component_name
        == "contactSearch"
    )
    assert result["plan"]["status"] == "DRAFT"


@pytest.mark.parametrize("change", ["target", "source", "plan"])
def test_review_hash_covers_org_plan_and_files(service, change):
    package, _ = generate(service)

    if change == "target":
        package["targetOrg"] = "AnotherOrg"
    elif change == "source":
        package["files"][next(iter(package["files"]))] += " changed"
    else:
        package["plan"]["summary"] = "Changed intent"

    with pytest.raises(ValueError, match="fingerprint"):
        service.verify_package(package)


def test_existing_code_is_never_reclassified_as_create(service):
    service.cli.return_value = {
        "result": [{"fullName": "ContactSearchService"}]
    }

    with pytest.raises(ValueError, match="already exists"):
        generate(service)


def test_updates_do_not_silently_generate_creates(service):
    plan = deepcopy(PLAN)
    plan["items"][0]["action"] = "UPDATE"

    with pytest.raises(ValueError, match="new components only"):
        generate(service, plan)


def test_planner_does_not_ignore_unsupported_components(service):
    plan = deepcopy(PLAN)
    plan["items"] = [
        {
            "id": "TAB-1",
            "action": "CREATE",
            "metadataType": "CustomTab",
            "fullName": "ContactTab",
            "config": {},
        }
    ]

    with pytest.raises(ValueError, match="not connected"):
        generate(service, plan)


def test_all_apex_components_must_be_generated(service):
    plan = deepcopy(PLAN)
    plan["items"].append(
        {
            "id": "APEX-2",
            "action": "CREATE",
            "metadataType": "ApexClass",
            "fullName": "AnotherService",
            "config": {"apexKind": "Service"},
        }
    )

    with pytest.raises(ValueError, match="omitted"):
        generate(service, plan)


def test_deploy_uses_exact_saved_files_and_specified_tests(
    service,
    monkeypatch,
):
    package, _ = generate(service)

    monkeypatch.setattr(service, "ensure_new", Mock())
    monkeypatch.setattr(
        "Backend.AI.app.services.metadata_service."
        "FlowPreflightService.validate",
        Mock(),
    )

    service.cli.return_value = success()
    package["layoutReady"] = True
    package["approvedHash"] = package["sourceHash"]

    service.deploy(package, dry_run=True)
    args = service.cli.call_args.args[0]

    assert "--dry-run" in args
    assert args[args.index("--test-level") + 1] == "RunSpecifiedTests"
    assert args[args.index("--tests") + 1] == "ContactSearchServiceTest"


def test_default_flow_generation_uses_existing_validated_flow_contract(
    service,
):
    from Backend.AI.app.tests.test_flow_pipeline import plan_data, fields

    metadata = service.metadata_factory("AIOrg")
    metadata.find_relevant_objects.return_value = ["Account"]
    metadata.get_context.return_value = {
        "objects": [{"name": "Account", "fields": fields()}]
    }

    provider = Mock()
    provider.generate.return_value = json.dumps(plan_data("DRAFT"))

    package = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement=(
                "Default blank Account descriptions with a before-save flow"
            )
        ),
        provider,
    )

    assert any(
        path.endswith(".flow-meta.xml")
        for path in package["files"]
    )
    assert package["plan"]["status"] == "DRAFT"
    assert provider.generate.call_count == 1
    assert package["testClasses"] == []


def test_non_apex_validation_does_not_require_apex_test_results(service):
    service.check_tests(
        {
            "components": [
                {
                    "metadataType": "LightningComponentBundle",
                    "fullName": "contactSearch",
                }
            ]
        },
        {"result": {"success": True, "done": True}},
    )


def test_invalid_scope_does_not_call_ai(service):
    service.cli.side_effect = RuntimeError("Org unavailable")
    provider = Mock()

    with pytest.raises(RuntimeError):
        service.generate(
            ImplementationRequest(target_org="AIOrg", requirement="Build UI"),
            provider,
        )

    provider.generate.assert_not_called()


def test_metadata_preview_generates_xml_without_persisting_user_approval(
    service,
    monkeypatch,
):
    from Backend.AI.app.validators.metadata_spec_validator import (
        MetadataSpecification,
    )

    plan = deepcopy(PLAN)
    plan["items"] = [
        {
            "id": "FIELD-1",
            "action": "CREATE",
            "metadataType": "CustomField",
            "fullName": "Contact.Review_Note__c",
            "label": "Review Note",
            "config": {"type": "Text", "length": 80},
        }
    ]

    seen = []

    def specification(self, preview, salesforce_context):
        seen.append(preview)

        return MetadataSpecification.model_validate(
            {
                "planId": preview.id,
                "metadata": [
                    {
                        "itemId": "FIELD-1",
                        "action": "CREATE",
                        "metadataType": "CustomField",
                        "fullName": "Contact.Review_Note__c",
                        "label": "Review Note",
                        "config": {"type": "Text", "length": 80},
                    }
                ],
            }
        )

    monkeypatch.setattr(
        "Backend.AI.app.services.metadata_service."
        "MetadataService.generate_specification",
        specification,
    )

    provider = Mock()
    provider.generate.return_value = json.dumps(plan)

    package = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement="Create a Review Note text field on Contact"
        ),
        provider,
    )

    assert (
        "force-app/main/default/objects/Contact/fields/"
        "Review_Note__c.field-meta.xml"
    ) in package["files"]

    assert package["plan"]["status"] == "DRAFT"
    assert package["plan"]["items"][0]["approval"] == "PENDING"
    assert seen[0].status == "APPROVED"
    assert all(
        call.args[0][0] == "org"
        for call in service.cli.call_args_list
    )


def test_existing_endpoints_approve_validate_and_deploy(
    tmp_path,
    service,
    monkeypatch,
):
    import Backend.AI.app.main as main
    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    from Backend.AI.app.services.layout_selection_service import (
        LayoutSelectionWorkflow,
    )
    from Backend.AI.app.validators.plan_validator import ImplementationPlan

    store = PlanStore()
    packages = MetadataSpecStore()
    workflow = LayoutSelectionWorkflow(store, tmp_path)

    monkeypatch.setattr(main, "plan_store", store)
    monkeypatch.setattr(main, "metadata_spec_store", packages)
    monkeypatch.setattr(main, "layout_workflow", workflow)
    monkeypatch.setattr(main, "default_pipeline", service)

    package, _ = generate(service)
    plan = ImplementationPlan.model_validate(package["plan"])
    store.save(plan)

    package = service.prepare_review(package, plan, {})
    package.update(state="validated", validatedHash=package["sourceHash"])
    packages.save_package(package)

    client = TestClient(main.app)
    path = "/api/plans/" + plan.id

    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 422

    assert client.post(
        path + "/approve",
        json={"source_hash": "x" * 64},
    ).status_code == 422

    assert client.post(
        path + "/approve",
        json={"source_hash": package["sourceHash"]},
    ).status_code == 200

    report = success()
    report["result"]["checkOnly"] = False
    service.deploy = Mock(return_value=report)
    response = client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]})

    assert response.status_code == 200
    assert response.json()["state"] == "deployed"
    assert service.deploy.call_count == 1
    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 409
    assert client.get(path).json()["approvedHash"] == package["sourceHash"]


def test_fls_and_layout_files_are_reviewed_before_approval(
    service,
    monkeypatch,
):
    import xml.etree.ElementTree as ET

    from Backend.AI.app.validators.plan_validator import ImplementationPlan
    from Backend.AI.app.validators.metadata_spec_validator import (
        MetadataSpecification,
    )
    from Backend.AI.app.services.page_layout_service import (
        new_layout,
        layout_path,
        write_xml,
        Q,
    )

    plan = deepcopy(PLAN)
    plan["items"] = [
        {
            "id": "F1",
            "action": "CREATE",
            "metadataType": "CustomField",
            "fullName": "Contact.Review_Note__c",
            "label": "Review Note",
            "config": {"type": "Text", "length": 80},
        }
    ]

    def specification(self, preview, salesforce_context):
        return MetadataSpecification.model_validate(
            {
                "planId": preview.id,
                "metadata": [
                    {
                        "itemId": "F1",
                        "action": "CREATE",
                        "metadataType": "CustomField",
                        "fullName": "Contact.Review_Note__c",
                        "label": "Review Note",
                        "config": {"type": "Text", "length": 80},
                    }
                ],
            }
        )

    monkeypatch.setattr(
        "Backend.AI.app.services.metadata_service."
        "MetadataService.generate_specification",
        specification,
    )

    def retrieve(self, root, objects=None):
        layout = new_layout(ET.Element(Q("CustomObject")))
        write_xml(
            layout,
            root / layout_path("Contact-Contact Layout"),
        )

        profile = ET.Element(Q("Profile"))
        assignment = ET.SubElement(profile, Q("layoutAssignments"))
        ET.SubElement(assignment, Q("layout")).text = (
            "Contact-Contact Layout"
        )

        return profile, {"Contact-Contact Layout"}

    monkeypatch.setattr(
        "Backend.AI.app.services.page_layout_service."
        "PageLayoutService._retrieve",
        retrieve,
    )

    provider = Mock()
    provider.generate.return_value = json.dumps(plan)

    package = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement="Create Contact Review Note"
        ),
        provider,
    )

    draft = ImplementationPlan.model_validate(package["plan"])

    reviewed = service.prepare_review(
        package,
        draft,
        {
            "Contact": [
                {
                    "fullName": "Contact-Contact Layout",
                    "sectionId": "0",
                }
            ]
        },
    )

    assert reviewed["sourceHash"] != package["sourceHash"]

    assert (
        "force-app/main/default/profiles/Admin.profile-meta.xml"
    ) in reviewed["files"]

    assert (
        "force-app/main/default/layouts/"
        "Contact-Contact Layout.layout-meta.xml"
    ) in reviewed["files"]

    assert reviewed["systemAdministratorFLS"]["fieldPermissions"] == [
        {
            "field": "Contact.Review_Note__c",
            "readable": True,
            "editable": True,
        }
    ]

    assert draft.status == "DRAFT"
    assert reviewed["layoutReady"]

    reviewed["approvedHash"] = reviewed["sourceHash"]

    monkeypatch.setattr(service, "ensure_new", Mock())
    monkeypatch.setattr(
        "Backend.AI.app.services.metadata_service."
        "FlowPreflightService.validate",
        Mock(),
    )

    def cli(args, root):
        files = {
            path.relative_to(root).as_posix(): path.read_text()
            for path in (root / "force-app").rglob("*")
            if path.is_file()
        }

        assert files == reviewed["files"]

        return {"result": {"success": True, "done": True}}

    service.cli = cli
    assert service.deploy(reviewed, dry_run=True)["result"]["success"]


@pytest.fixture
def default_api(tmp_path, service, monkeypatch):
    import Backend.AI.app.main as main

    from Backend.AI.app.services.plan_store import PlanStore
    from Backend.AI.app.services.metadata_spec_store import MetadataSpecStore
    from Backend.AI.app.services.layout_selection_service import (
        LayoutSelectionWorkflow,
    )
    from Backend.AI.app.validators.plan_validator import ImplementationPlan

    store = PlanStore()
    packages = MetadataSpecStore()
    workflow = LayoutSelectionWorkflow(store, tmp_path)

    monkeypatch.setattr(main, "plan_store", store)
    monkeypatch.setattr(main, "metadata_spec_store", packages)
    monkeypatch.setattr(main, "layout_workflow", workflow)
    monkeypatch.setattr(main, "default_pipeline", service)

    package, _ = generate(service)
    plan = ImplementationPlan.model_validate(package["plan"])
    store.save(plan)

    package = service.prepare_review(package, plan, {})
    package.update(state="validated", validatedHash=package["sourceHash"])
    packages.save_package(package)

    client = TestClient(main.app)
    path = "/api/plans/" + plan.id

    assert client.post(
        path + "/approve",
        json={"source_hash": package["sourceHash"]},
    ).status_code == 200

    return client, path, packages, plan


def test_failed_default_validation_never_deploys(default_api, service):
    client, path, packages, plan = default_api
    bundle=packages.get_package(plan.id)
    bundle.update(state="generated", validatedHash=None, approvedHash=None)
    packages.save_package(bundle)
    plan.status="DRAFT"
    for item in plan.items: item.approval="PENDING"

    service.deploy = Mock(
        return_value={"result": {"success": False, "done": True}}
    )

    assert client.post(path + "/validate", json={"source_hash": client.get(path).json()["sourceHash"]}).json()["state"] == "failed"
    assert service.deploy.call_count == 1


def test_pending_default_validation_never_deploys(default_api, service):
    client, path, packages, plan = default_api
    bundle=packages.get_package(plan.id)
    bundle.update(state="generated", validatedHash=None, approvedHash=None)
    packages.save_package(bundle)
    plan.status="DRAFT"
    for item in plan.items: item.approval="PENDING"

    service.deploy = Mock(
        return_value={
            "result": {
                "id": "0Af000000000001AAA",
                "done": False,
                "status": "InProgress",
            }
        }
    )

    assert client.post(path + "/validate", json={"source_hash": client.get(path).json()["sourceHash"]}).json()["state"] == "pending"
    assert service.deploy.call_count == 1
    assert client.post(path + "/validate", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 409


def test_missing_apex_test_execution_blocks_real_deploy(
    default_api,
    service,
):
    client, path, _, _ = default_api

    service.deploy = Mock(
        return_value={"result": {"success": True, "done": True}}
    )

    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).json()["state"] == "unknown"
    assert service.deploy.call_count == 1


def test_unknown_real_deploy_blocks_retry(default_api, service):
    client, path, _, _ = default_api

    service.deploy = Mock(
        side_effect=RuntimeError("Lost response")
    )

    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 502
    assert client.get(path).json()["state"] == "unknown"
    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 409


def test_default_general_input_saves_into_existing_plan_store(
    default_api,
    service,
    monkeypatch,
):
    import Backend.AI.app.main as main

    client, _, packages, _ = default_api
    provider = Mock()
    provider.generate.side_effect = [
        json.dumps(PLAN),
        json.dumps(SOURCE),
    ]

    monkeypatch.setattr(
        main,
        "get_ai_provider",
        lambda: provider,
    )

    response = client.post(
        "/api/plan",
        json={
            "requirement": "Build a Contact search Apex service",
            "target_org": "AIOrg",
            "generate_files": True,
        },
    )

    assert response.status_code == 200
    package = response.json()

    assert package["id"] == package["plan"]["id"]
    assert main.plan_store.get(package["id"]).status == "DRAFT"

    assert packages.get_package(package["id"])["files"] == (
        package["files"]
    )

    assert package["layoutReady"]


def test_approval_rejects_changed_plan(default_api):
    client, path, _, plan = default_api
    plan.summary = "Changed after approval"

    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 422


def test_default_lwc_generation_runs_existing_real_compiler(service):
    from Backend.AI.app.services.lwc_service import LWCAutomationService
    from Backend.AI.app.tests.test_lwc_enhanced import HTML, JS, CTX

    metadata = service.metadata_factory("AIOrg")
    metadata.find_relevant_objects.return_value = ["Account"]
    metadata.get_context.return_value = deepcopy(CTX)

    service.lwc_service = LWCAutomationService(
        service.project_root,
        metadata_factory=lambda org: metadata,
        tooling_root=Path(__file__).resolve().parents[4],
    )

    plan = deepcopy(PLAN)
    plan["items"] = [
        {
            "id": "UI1",
            "action": "CREATE",
            "metadataType": "LightningComponentBundle",
            "fullName": "accountSearch",
            "config": {
                "isExposed": True,
                "targets": ["lightning__AppPage"],
            },
        }
    ]

    provider = Mock()
    provider.generate.side_effect = [
        json.dumps(plan),
        json.dumps(
            {
                "html": HTML,
                "javascript": JS,
                "css": ":host { display:block; }",
            }
        ),
    ]

    package = service.generate(
        ImplementationRequest(target_org="AIOrg",
            requirement="Search Account records on an App Page"
        ),
        provider,
    )

    assert len(package["files"]) == 4
    assert package["components"] == [
        {
            "metadataType": "LightningComponentBundle",
            "fullName": "accountSearch",
        }
    ]
    assert package["testClasses"] == []
    assert package["plan"]["status"] == "DRAFT"


def test_incomplete_real_deploy_response_blocks_retry(
    default_api,
    service,
):
    client, path, _, _ = default_api

    service.deploy = Mock(
        side_effect=[
            success(),
            {"result": {"id": "0Af000000000001AAA"}},
        ]
    )

    response = client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]})

    assert response.status_code == 200
    assert response.json()["state"] == "unknown"
    assert client.post(path + "/deploy", json={"source_hash": client.get(path).json()["sourceHash"]}).status_code == 409