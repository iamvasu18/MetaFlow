"""Run with pytest, or python -m unittest <module>. Salesforce calls are mocked."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from Backend.AI.app.services.page_layout_service import (
    PageLayoutService, Q, PROFILE_PATH, layout_path, add_fields,
    select_default_layout, new_layout, write_xml,
)
from Backend.AI.app.services.profile_fls_service import NS, component_path, SystemAdministratorFLSService
from Backend.AI.app.services.deployment_service import SalesforceDeploymentService


def xml(tag, content):
    return ET.fromstring(f'<{tag} xmlns="{NS}">{content}</{tag}>')


def field(name="Test__c", kind="Text", extra=""):
    return xml("CustomField", f'<fullName>{name}</fullName><type>{kind}</type>{extra}')


def layout(label="Information"):
    root = new_layout(xml("CustomObject", '<nameField><type>Text</type></nameField>'))
    root.find(f'{Q("layoutSections")}/{Q("label")}').text = label
    ET.SubElement(root, Q("excludeButtons")).text = "Delete"
    return root


def profile(default=False):
    body = '<layoutAssignments><layout>Account-Account Layout</layout></layoutAssignments><layoutAssignments><layout>Contact-Contact Layout</layout></layoutAssignments>'
    if default:
        body += '<layoutAssignments><layout>Account-Business Layout</layout><recordType>Account.Business</recordType></layoutAssignments><recordTypeVisibilities><default>true</default><recordType>Account.Business</recordType><visible>true</visible></recordTypeVisibilities>'
    return xml("Profile", body)


class PageLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'sfdx-project.json').write_text(json.dumps({'sourceApiVersion': '65.0'}))
        self.item = Obj(action='CREATE', metadataType='CustomField', fullName='Account.Test__c')
        self.spec = Obj(metadata=[self.item])
        write_xml(field(), self.root / component_path('CustomField', self.item.fullName))

    def retrieve_fixture(self, directory, objects=None):
        write_xml(layout('Account Information'), directory / layout_path('Account-Account Layout'))
        return profile(), {'Account-Account Layout', 'Contact-Contact Layout'}

    def test_existing_contents_and_column_structure_preserved(self):
        root = layout()
        before = deepcopy(root)
        added, skipped = add_fields(root, [('Test__c', field())])
        self.assertEqual(added, ['Test__c'])
        self.assertEqual(skipped, [])
        for column in root.findall(f'{Q("layoutSections")}/{Q("layoutColumns")}'):
            for item in list(column):
                if item.findtext(Q('field')) == 'Test__c':
                    column.remove(item)
        self.assertEqual(ET.tostring(root), ET.tostring(before))

    def test_duplicate_anywhere_not_added(self):
        root = layout()
        add_fields(root, [('Test__c', field())])
        self.assertEqual(add_fields(root, [('Test__c', field())]), ([], ['Test__c']))
        self.assertEqual(len([n for n in root.iter(Q('field')) if n.text == 'Test__c']), 1)

    def test_behaviors(self):
        for kind, extra, expected in [('Text', '', 'Edit'), ('Number', '<formula>1+1</formula>', 'Readonly'), ('Summary', '', 'Readonly'), ('AutoNumber', '', 'Readonly'), ('Text', '<required>true</required>', 'Required'), ('MasterDetail', '', 'Required')]:
            with self.subTest(kind=kind, extra=extra):
                root = layout()
                add_fields(root, [('Test__c', field(kind=kind, extra=extra))])
                entry = next(n for n in root.iter(Q('layoutItems')) if n.findtext(Q('field')) == 'Test__c')
                self.assertEqual(entry.findtext(Q('behavior')), expected)

    def test_standard_information_ignores_system_information(self):
        root = layout('Account Information')
        section = deepcopy(root.find(Q('layoutSections')))
        section.find(Q('label')).text = 'System Information'
        root.append(section)
        add_fields(root, [('Test__c', field())])
        self.assertFalse(any(n.text == 'Test__c' for n in section.iter(Q('field'))))

    def test_missing_or_ambiguous_section_stops(self):
        root = layout('Details')
        with self.assertRaisesRegex(ValueError, 'Information'):
            add_fields(root, [('Test__c', field())])
        root = layout()
        root.append(deepcopy(root.find(Q('layoutSections'))))
        with self.assertRaisesRegex(ValueError, 'Information'):
            add_fields(root, [('Test__c', field())])

    def test_record_type_default_selects_correct_layout(self):
        self.assertEqual(select_default_layout(profile(True), 'Account'), 'Account-Business Layout')
        self.assertEqual(select_default_layout(profile(), 'Account'), 'Account-Account Layout')

    def test_unknown_assignment_fails(self):
        with self.assertRaises(ValueError):
            select_default_layout(profile(), 'Opportunity')

    def test_generate_preserves_fls_and_all_assignments(self):
        SystemAdministratorFLSService(self.root).generate(self.spec)
        with patch.object(PageLayoutService, '_retrieve', side_effect=self.retrieve_fixture):
            result = PageLayoutService(self.root).generate(self.spec)
        overlay = ET.parse(self.root / PROFILE_PATH).getroot()
        self.assertEqual(len(overlay.findall(Q('fieldPermissions'))), 1)
        self.assertEqual(len(overlay.findall(Q('layoutAssignments'))), 2)
        self.assertEqual(result['layouts'][0]['addedFields'], ['Test__c'])
        self.assertFalse((self.root / layout_path('Contact-Contact Layout')).exists())
        plan = Obj(status='APPROVED', items=[self.item])
        files = [component_path('CustomField', self.item.fullName).as_posix(), *result['generatedFiles']]
        command = SalesforceDeploymentService(project_root=self.root).build_deploy_command(plan, {'valid': True, 'deploymentFiles': files, 'pageLayouts': result})
        self.assertEqual(command.count('--source-dir'), 3)
        self.assertIn(str((self.root / layout_path('Account-Account Layout')).resolve()), command)

    def test_required_field_still_gets_profile_assignment(self):
        write_xml(field(extra='<required>true</required>'), self.root / component_path('CustomField', self.item.fullName))
        self.assertEqual(SystemAdministratorFLSService(self.root).generate(self.spec)['generatedFiles'], [])
        with patch.object(PageLayoutService, '_retrieve', side_effect=self.retrieve_fixture):
            PageLayoutService(self.root).generate(self.spec)
        self.assertTrue((self.root / PROFILE_PATH).is_file())

    def test_new_object_layout_and_assignment(self):
        item = Obj(action='CREATE', metadataType='CustomObject', fullName='Training__c')
        write_xml(xml('CustomObject', '<nameField><type>AutoNumber</type></nameField>'), self.root / component_path('CustomObject', item.fullName))
        with patch.object(PageLayoutService, '_retrieve', return_value=(profile(), set())):
            result = PageLayoutService(self.root).generate(Obj(metadata=[item]))
        self.assertTrue(result['layouts'][0]['created'])
        generated = ET.parse(self.root / result['generatedFiles'][0]).getroot()
        self.assertEqual(next(generated.iter(Q('behavior'))).text, 'Readonly')
        overlay = ET.parse(self.root / PROFILE_PATH).getroot()
        self.assertIn('Training__c-Training Layout', [n.text for n in overlay.iter(Q('layout'))])

    def test_population_layout_name_matches_profile_and_file(self):
        item = Obj(action='CREATE', metadataType='CustomObject', fullName='Population__c')
        write_xml(xml('CustomObject', '<nameField><type>Text</type></nameField>'), self.root / component_path('CustomObject', item.fullName))
        with patch.object(PageLayoutService, '_retrieve', return_value=(profile(), set())):
            result = PageLayoutService(self.root).generate(Obj(metadata=[item]))
        expected = 'Population__c-Population Layout'
        self.assertEqual(result['layouts'][0]['fullName'], expected)
        self.assertTrue((self.root / layout_path(expected)).is_file())
        overlay = ET.parse(self.root / PROFILE_PATH).getroot()
        self.assertIn(expected, [n.text for n in overlay.iter(Q('layout'))])
        self.assertNotIn('__', expected.partition('-')[2])

    def test_validation_rule_only_does_not_retrieve(self):
        with patch.object(PageLayoutService, '_retrieve') as retrieve:
            result = PageLayoutService(self.root).generate(Obj(metadata=[Obj(action='CREATE', metadataType='ValidationRule')]))
        retrieve.assert_not_called()
        self.assertEqual(result['generatedFiles'], [])

    def test_unrelated_and_missing_layout_rejected(self):
        result = {'valid': True, 'deploymentFiles': [component_path('CustomField', self.item.fullName).as_posix()], 'pageLayouts': {'layouts': [{'fullName': 'Contact-Contact Layout', 'object': 'Contact'}]}}
        service = SalesforceDeploymentService(project_root=self.root)
        plan = Obj(status='APPROVED', items=[self.item])
        with self.assertRaisesRegex(ValueError, 'approved'):
            service.build_deploy_command(plan, result)
        result['pageLayouts']['layouts'] = [{'fullName': 'Account-Account Layout', 'object': 'Account'}]
        with self.assertRaises(ValueError):
            service.build_deploy_command(plan, result)

    def test_unsafe_layout_path_rejected(self):
        for name in ['Account-../../oops', 'Account-..\\oops', 'Account-Bad:Name']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                layout_path(name)

    def test_retrieve_manifest_and_completion(self):
        calls = []
        def cli(root, args):
            calls.append(args)
            if args[:3] == ['org', 'list', 'metadata']:
                return [{'fullName': 'Account-Account Layout' if args[-1] == 'Layout' else 'Account.Business'}]
            write_xml(profile(), root / PROFILE_PATH)
            return {'success': True, 'done': True}
        service = PageLayoutService(self.root)
        with patch.object(service, '_cli', side_effect=cli):
            service._retrieve(self.root)
        package = ET.parse(self.root / 'layout-retrieve.xml').getroot()
        self.assertEqual({n.findtext(Q('name')) for n in package.findall(Q('types'))}, {'Profile', 'Layout', 'RecordType'})
        self.assertEqual(len(calls), 3)

    def test_cli_error_prevents_generation(self):
        with patch('shutil.which', return_value='sf'), patch('subprocess.run', return_value=Obj(returncode=1, stdout='{"status":1,"message":"Denied"}', stderr='')):
            with self.assertRaisesRegex(RuntimeError, 'Denied'):
                PageLayoutService(self.root)._cli(self.root, ['org', 'list', 'metadata'])


if __name__ == '__main__':
    unittest.main()
