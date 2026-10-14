from pathlib import Path

from Backend.AI.app.services.apex_generator import generate_apex
from Backend.AI.app.services.metadata_generator import SalesforceMetadataGenerator
from Backend.AI.app.services.metadata_validator import SalesforceMetadataValidator
from Backend.AI.app.services.salesforce_capability_registry import SalesforceCapabilityRegistry
from Backend.AI.app.validators.metadata_spec_validator import validate_metadata_spec
from Backend.AI.app.validators.plan_validator import validate_plan, ImplementationPlan


def class_item(body=None):
    return {
        "itemId": "ITEM-APEX-CLASS",
        "action": "CREATE",
        "metadataType": "ApexClass",
        "fullName": "AccountService",
        "label": "Account Service",
        "config": {
            "apexKind": "Service",
            **({"body": body} if body is not None else {}),
        },
    }


def trigger_item(body=None):
    return {
        "itemId": "ITEM-APEX-TRIGGER",
        "action": "CREATE",
        "metadataType": "ApexTrigger",
        "fullName": "AccountTrigger",
        "config": {
            "sobject": "Account",
            "events": ["before insert", "before update"],
            **({"body": body} if body is not None else {}),
        },
    }


def test_apex_capabilities_are_executable():
    assert SalesforceCapabilityRegistry.is_executable_metadata_type("ApexClass")
    assert SalesforceCapabilityRegistry.is_executable_metadata_type("ApexTrigger")


def test_plan_accepts_apex_without_source_body():
    plan = {
        "id": "PLAN-APEX-001",
        "requirementId": "REQ-APEX-001",
        "summary": "Create an Account service",
        "status": "APPROVED",
        "items": [class_item()],
    }
    plan["items"][0]["id"] = plan["items"][0].pop("itemId")
    result = validate_plan(plan)
    assert result.valid
    assert result.errors == []


def test_plan_validates_apex_trigger_contract():
    trigger = trigger_item()
    trigger["id"] = trigger.pop("itemId")
    result = validate_plan({
        "id": "PLAN-APEX-002",
        "requirementId": "REQ-APEX-002",
        "summary": "Create Account trigger",
        "status": "APPROVED",
        "items": [trigger],
    })
    assert result.valid


def test_metadata_spec_accepts_apex_class():
    item = class_item("public with sharing class AccountService { public static void run(List<Account> records) { } }")
    data = {"planId": "PLAN-APEX-003", "metadata": [item], "validationIssues": []}
    result = validate_metadata_spec(data)
    assert result.valid, result.errors


def test_metadata_spec_rejects_mismatched_class_name():
    item = class_item("public with sharing class WrongName { }")
    data = {"planId": "PLAN-APEX-004", "metadata": [item], "validationIssues": []}
    result = validate_metadata_spec(data)
    assert not result.valid
    assert any("does not match fullName" in error for error in result.errors)


def test_metadata_spec_accepts_apex_trigger():
    body = "trigger AccountTrigger on Account (before insert, before update) { for (Account a : Trigger.new) { a.Description = 'X'; } }"
    item = trigger_item(body)
    result = validate_metadata_spec({
        "planId": "PLAN-APEX-005",
        "metadata": [item],
        "validationIssues": [],
    })
    assert result.valid, result.errors


def test_apex_generator_creates_class_and_meta(tmp_path: Path):
    (tmp_path / "sfdx-project.json").write_text('{"sourceApiVersion":"67.0"}', encoding="utf-8")
    raw = class_item("public with sharing class AccountService { public static void run() {} }")
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    item = type("Item", (), raw)()
    item.metadataType = "ApexClass"
    path = generate_apex(item, tmp_path)
    assert path == tmp_path / "force-app/main/default/classes/AccountService.cls"
    assert path.read_text(encoding="utf-8").startswith("public with sharing class AccountService")
    meta = path.with_name("AccountService.cls-meta.xml")
    assert meta.exists()
    assert "<apiVersion>67.0</apiVersion>" in meta.read_text(encoding="utf-8")


def test_apex_generator_creates_trigger_and_meta(tmp_path: Path):
    (tmp_path / "sfdx-project.json").write_text('{"sourceApiVersion":"67.0"}', encoding="utf-8")
    body = "trigger AccountTrigger on Account (before insert, before update) { }"
    raw = trigger_item(body)
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    item = type("Item", (), raw)()
    path = generate_apex(item, tmp_path)
    assert path == tmp_path / "force-app/main/default/triggers/AccountTrigger.trigger"
    assert path.with_name("AccountTrigger.trigger-meta.xml").exists()


def test_metadata_generator_routes_apex(tmp_path: Path):
    (tmp_path / "sfdx-project.json").write_text('{"sourceApiVersion":"67.0"}', encoding="utf-8")
    raw = class_item("public with sharing class AccountService { public static void run() {} }")
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    plan = ImplementationPlan.model_validate({
        "id": "PLAN-APEX-006",
        "requirementId": "REQ-APEX-006",
        "summary": "Create service",
        "status": "APPROVED",
        "items": [raw],
    })
    generated = SalesforceMetadataGenerator(project_root=tmp_path).generate(plan)
    assert generated == [str(tmp_path / "force-app/main/default/classes/AccountService.cls")]


def test_metadata_validator_validates_apex_source_and_meta(tmp_path: Path):
    (tmp_path / "sfdx-project.json").write_text('{"sourceApiVersion":"67.0"}', encoding="utf-8")
    raw = class_item("public with sharing class AccountService { public static void run() {} }")
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    plan = ImplementationPlan.model_validate({
        "id": "PLAN-APEX-007",
        "requirementId": "REQ-APEX-007",
        "summary": "Create service",
        "status": "APPROVED",
        "items": [raw],
    })
    SalesforceMetadataGenerator(project_root=tmp_path).generate(plan)
    result = SalesforceMetadataValidator(project_root=tmp_path).validate(plan)
    assert result["valid"], result["errors"]


def test_apex_component_paths_are_deployable():
    from Backend.AI.app.services.profile_fls_service import component_path
    assert component_path("ApexClass", "AccountService").as_posix().endswith("force-app/main/default/classes/AccountService.cls")
    assert component_path("ApexTrigger", "AccountTrigger").as_posix().endswith("force-app/main/default/triggers/AccountTrigger.trigger")


def test_apex_deployment_command_uses_exact_source_file(tmp_path: Path):
    from Backend.AI.app.services.deployment_service import SalesforceDeploymentService
    raw = class_item("public with sharing class AccountService { public static void run() {} }")
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    plan = ImplementationPlan.model_validate({
        "id": "PLAN-APEX-008",
        "requirementId": "REQ-APEX-008",
        "summary": "Create service",
        "status": "APPROVED",
        "items": [raw],
    })
    (tmp_path / 'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}',encoding='utf-8')
    test_raw = dict(raw, id='ITEM-APEX-TEST', fullName='AccountServiceTest', config={'apexKind':'Test','body':'@IsTest private class AccountServiceTest { @IsTest static void testRun() { AccountService.run(); System.assert(true); } }'})
    plan.items.append(type(plan.items[0]).model_validate(test_raw))
    test_source = generate_apex(plan.items[-1],tmp_path)
    source = tmp_path / "force-app/main/default/classes/AccountService.cls"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(raw["config"]["body"], encoding="utf-8")
    meta = source.with_name("AccountService.cls-meta.xml")
    meta.write_text('<?xml version="1.0" encoding="UTF-8"?><ApexClass xmlns="http://soap.sforce.com/2006/04/metadata"><apiVersion>67.0</apiVersion><status>Active</status></ApexClass>', encoding="utf-8")
    result = SalesforceDeploymentService(target_org="AIOrg", project_root=tmp_path).build_deploy_command(
        plan,
        {"valid": True, "deploymentFiles": [str(source),str(test_source)]},
    )
    assert result[0:6] == ["sf", "project", "deploy", "start", "--target-org", "AIOrg"]
    assert result[6:8] == ["--source-dir", str(source.resolve())]
    assert result[result.index('--test-level')+1] == 'RunSpecifiedTests'
    assert result[result.index('--tests')+1] == 'AccountServiceTest'


def test_metadata_service_accepts_ai_generated_apex_spec():
    from Backend.AI.app.services.metadata_service import MetadataService

    class Provider:
        def generate(self, *, system_prompt, user_prompt):
            import json
            return json.dumps({
                "planId": "PLAN-APEX-AI-001",
                "metadata": [{
                    "itemId": "ITEM-APEX-CLASS",
                    "action": "CREATE",
                    "metadataType": "ApexClass",
                    "fullName": "AccountService",
                    "label": "Account Service",
                    "description": None,
                    "dependencies": [],
                    "config": {
                        "apexKind": "Service",
                        "body": "public with sharing class AccountService { public static void run() {} }",
                    },
                }],
                "validationIssues": [],
            })

    raw = class_item()
    raw["id"] = raw.pop("itemId")
    raw["approval"] = "APPROVED"
    plan = ImplementationPlan.model_validate({
        "id": "PLAN-APEX-AI-001",
        "requirementId": "REQ-APEX-AI-001",
        "summary": "Create Account service",
        "status": "APPROVED",
        "items": [raw],
    })
    spec = MetadataService(provider=Provider()).generate_specification(plan, {"objects": []})
    assert spec.planId == plan.id
    assert spec.metadata[0].metadataType == "ApexClass"
