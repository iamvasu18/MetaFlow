import ast
import json
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest.mock import Mock
import tempfile
import xml.etree.ElementTree as ET

from Backend.AI.app.services.page_layout_service import PageLayoutService, new_layout, write_xml, layout_path

from Backend.AI.app.services.layout_selection_service import LayoutSelectionWorkflow

import pytest
from Backend.AI.app.services.profile_fls_service import (
    NS, SystemAdministratorFLSService, component_path,
    initialize_deployment_project, validate_create_specification,
)
from Backend.AI.app.services.deployment_service import SalesforceDeploymentService
from Backend.AI.app.services.deployment_executor import SalesforceDeploymentExecutor


def fixture_plan(kind="Text", required=False, formula=False, field="Account.Test__c"):
    item = Obj(id="I1", itemId="I1", action="CREATE", approval="APPROVED", metadataType="CustomField", fullName=field)
    plan = Obj(id="P1", status="APPROVED", items=[item])
    spec = Obj(planId="P1", metadata=[item], validationIssues=[], model_dump=lambda: {})
    xml = f'<CustomField xmlns="{NS}"><fullName>{field.split(".")[1]}</fullName><type>{kind}</type><required>{str(required).lower()}</required>'
    if formula:
        xml += '<formula>1+1</formula>'
    return plan, spec, xml + '</CustomField>'


def write_field(root, spec, xml):
    path = root / component_path("CustomField", spec.metadata[0].fullName)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml)
    return path


@pytest.mark.parametrize("kind,formula,editable", [("Email", False, True), ("Checkbox", False, True), ("Number", True, False), ("Summary", False, False), ("AutoNumber", False, False), ("Lookup", False, True)])
def test_xml_controls_fls(tmp_path, kind, formula, editable):
    plan, spec, xml = fixture_plan(kind=kind, formula=formula)
    write_field(tmp_path, spec, xml)
    result = SystemAdministratorFLSService(tmp_path).generate(spec)
    assert result['fieldPermissions'] == [{'field': 'Account.Test__c', 'readable': True, 'editable': editable}]
    profile = ET.parse(tmp_path / result['generatedFiles'][0]).getroot()
    assert [node.tag for node in profile] == [f'{{{NS}}}fieldPermissions']
    assert profile.findtext(f'{{{NS}}}fieldPermissions/{{{NS}}}readable') == 'true'


@pytest.mark.parametrize("kind,required", [("Text", True), ("MasterDetail", False)])
def test_nonpermissionable_fields_are_reported_without_profile(tmp_path, kind, required):
    _, spec, xml = fixture_plan(kind=kind, required=required)
    write_field(tmp_path, spec, xml)
    result = SystemAdministratorFLSService(tmp_path).generate(spec)
    assert result['generatedFiles'] == []
    assert len(result['skippedFields']) == 1


def test_field_name_mismatch_stops_generation(tmp_path):
    _, spec, xml = fixture_plan()
    write_field(tmp_path, spec, xml.replace('Test__c</fullName>', 'Wrong__c</fullName>'))
    with pytest.raises(ValueError, match="does not match"):
        SystemAdministratorFLSService(tmp_path).generate(spec)


def test_stale_spec_rejected():
    plan, spec, _ = fixture_plan()
    spec.metadata = [Obj(itemId='I1', action='CREATE', metadataType='CustomField', fullName='Account.Other__c')]
    with pytest.raises(ValueError, match='does not match'):
        validate_create_specification(plan, spec)


def test_valid_spec_and_unapproved_item():
    plan, spec, _ = fixture_plan()
    validate_create_specification(plan, spec)
    plan.items[0].approval = 'DRAFT'
    with pytest.raises(ValueError, match='not approved'):
        validate_create_specification(plan, spec)


def test_project_preserves_version_and_namespace(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'sfdx-project.json').write_text(json.dumps({'sourceApiVersion': '67.0', 'namespace': 'Example', 'packageDirectories': [{'path': 'old'}]}))
    stage = tmp_path / 'stage'
    initialize_deployment_project(source, stage)
    config = json.loads((stage / 'sfdx-project.json').read_text())
    assert config == {'sourceApiVersion': '67.0', 'namespace': 'Example', 'packageDirectories': [{'path': 'force-app', 'default': True}]}


def test_command_contains_only_planned_field_and_admin_profile(tmp_path):
    plan, spec, xml = fixture_plan()
    field = write_field(tmp_path, spec, xml)
    fls = SystemAdministratorFLSService(tmp_path).generate(spec)
    stale = tmp_path / 'force-app/main/default/profiles/Other.profile-meta.xml'
    stale.write_text('<Profile/>')
    files = [str(field.relative_to(tmp_path))] + fls['generatedFiles']
    service = SalesforceDeploymentService(project_root=str(tmp_path))
    command = service.build_deploy_command(plan, {'valid': True, 'deploymentFiles': files})
    sources = [command[i+1] for i, v in enumerate(command) if v == '--source-dir']
    assert set(sources) == {str(tmp_path / f) for f in files}
    with pytest.raises(ValueError, match='Unexpected'):
        service.build_deploy_command(plan, {'valid': True, 'deploymentFiles': files + [str(stale)]})


def test_validation_rule_only_command(tmp_path):
    item = Obj(action='CREATE', metadataType='ValidationRule', fullName='Account.Require_Terms')
    plan = Obj(status='APPROVED', items=[item])
    service = SalesforceDeploymentService(project_root=str(tmp_path))
    command = service.build_deploy_command(plan, {'valid': True})
    assert str(tmp_path / 'force-app/main/default/objects/Account') in command


def test_missing_field_is_rejected(tmp_path):
    plan, _, _ = fixture_plan()
    with pytest.raises(ValueError, match='every approved'):
        SalesforceDeploymentService(project_root=str(tmp_path)).build_deploy_command(plan, {'valid': True, 'deploymentFiles': []})


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        component_path('CustomField', '../Account.Test__c')


@pytest.mark.parametrize('success', [True, False])
def test_executor_uses_project_cwd_and_real_completion(tmp_path, monkeypatch, success):
    plan, spec, xml = fixture_plan()
    field = write_field(tmp_path, spec, xml)
    monkeypatch.setattr('Backend.AI.app.services.deployment_executor.shutil.which', lambda _: 'sf')
    run = Mock(return_value=Obj(returncode=0, stdout=json.dumps({'status': 0, 'result': {'done': success, 'success': success}}), stderr=''))
    monkeypatch.setattr('Backend.AI.app.services.deployment_executor.subprocess.run', run)
    result = SalesforceDeploymentExecutor(project_root=str(tmp_path)).deploy(plan, {'valid': True, 'deploymentFiles': [str(field)]})
    assert result['success'] is success
    assert run.call_args.kwargs['cwd'] == str(tmp_path)


def test_endpoint_wires_fls_into_same_deployment(tmp_path, monkeypatch):
    # Compile the actual endpoint body, injecting collaborators to avoid a live
    # provider/org or importing unrelated application startup dependencies.
    source = Path(__file__).parents[1] / 'main.py'
    node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'deploy_plan')
    node.decorator_list = []
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code, self.detail = status_code, detail
    plan, spec, xml = fixture_plan(kind='Number', formula=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'sfdx-project.json').write_text('{"sourceApiVersion":"67.0"}')
    existing = tmp_path / 'force-app/main/default/profiles/Admin.profile-meta.xml'
    existing.parent.mkdir(parents=True)
    existing.write_text('original local profile')
    def retrieve_layouts(service, root, objects=None):
        layout = new_layout(ET.fromstring(f'<CustomObject xmlns="{NS}"><nameField><type>Text</type></nameField></CustomObject>'))
        write_xml(layout, root / layout_path('Account-Account Layout'))
        profile = ET.fromstring(f'<Profile xmlns="{NS}"><layoutAssignments><layout>Account-Account Layout</layout></layoutAssignments></Profile>')
        return profile, {'Account-Account Layout'}
    monkeypatch.setattr('Backend.AI.app.services.page_layout_service.PageLayoutService._retrieve', retrieve_layouts)
    plan.items[0].config = {}
    plan.status = 'DRAFT'
    workflow = LayoutSelectionWorkflow(Obj(get=lambda _: plan), tmp_path)
    assert workflow.options(plan.id)['ready']
    plan.status = 'APPROVED'
    seen = {}
    class Generator:
        def __init__(self, project_root): self.root = Path(project_root)
        def generate_from_specification(self, specification): write_field(self.root, specification, xml)
    class Validator:
        def __init__(self, project_root): pass
        def validate(self, plan): return {'valid': True}
    class Executor:
        def __init__(self, target_org, project_root): self.root = Path(project_root)
        def deploy(self, plan, validation_result):
            seen['stage'] = self.root
            seen['files'] = validation_result['deploymentFiles']
            profile = ET.parse(self.root / 'force-app/main/default/profiles/Admin.profile-meta.xml').getroot()
            assert profile.findtext(f'{{{NS}}}fieldPermissions/{{{NS}}}editable') == 'false'
            assert len(seen['files']) == 3
            assert profile.findtext(f'{{{NS}}}layoutAssignments/{{{NS}}}layout') == 'Account-Account Layout'
            command = SalesforceDeploymentService(project_root=self.root).build_deploy_command(plan, validation_result)
            assert command.count('--source-dir') == 3
            return {'success': True}
    from Backend.AI.app.main import DefaultApprovalRequest
    env = dict(DefaultApprovalRequest=DefaultApprovalRequest, require_legacy_workflow=lambda: None, target_org=lambda: 'AIOrg', Path=Path, tempfile=tempfile, HTTPException=HTTPException, layout_workflow=workflow,
        plan_store=Obj(get=lambda _: plan), metadata_spec_store=Obj(get=lambda _: spec),
        validate_create_specification=validate_create_specification,
        initialize_deployment_project=initialize_deployment_project, component_path=component_path,
        SystemAdministratorFLSService=SystemAdministratorFLSService,
        PageLayoutService=PageLayoutService,
        SalesforceMetadataGenerator=Generator, SalesforceMetadataValidator=Validator,
        SalesforceDeploymentExecutor=Executor)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), env)
    response = env['deploy_plan']('P1')
    assert response['pageLayouts']['layouts'][0]['addedFields'] == ['Test__c']
    assert response['systemAdministratorFLS']['profile'] == 'Admin'
    assert response['systemAdministratorFLS']['fieldPermissions'][0]['readable'] is True
    assert existing.read_text() == 'original local profile'
    assert not seen['stage'].exists()
