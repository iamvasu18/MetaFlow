import json
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from Backend.AI.app.services.custom_object_policy import apply_custom_object_defaults
from Backend.AI.app.services.planning_service import PlanningService
from Backend.AI.app.validators.plan_validator import validate_plan
from Backend.AI.app.prompts.prompt_builder import build_planning_prompt


def plan(config=None):
    return {'id':'PLAN-001','requirementId':'REQ-001','summary':'Create Population',
            'status':'DRAFT','assumptions':[], 'items':[{'id':'ITEM-001',
            'action':'CREATE','metadataType':'CustomObject','fullName':'Population__c',
            'label':'Population','approval':'PENDING','dependencies':[], 'config':config}]}


class CustomObjectDefaultsTests(unittest.TestCase):
    def test_population_readwrite_becomes_supported_default_before_validation(self):
        source = plan({'sharingModel':'ReadWrite'})
        result = apply_custom_object_defaults(source, 'Create a Population custom object')
        self.assertEqual(result['items'][0]['config']['sharingModel'], 'Read')
        self.assertEqual(source['items'][0]['config']['sharingModel'], 'ReadWrite')
        self.assertTrue(validate_plan(result).valid)

    def test_missing_defaults(self):
        result = apply_custom_object_defaults(plan(), 'Create a Population custom object')
        self.assertEqual(result['items'][0]['config'], {'nameFieldType':'Text','deploymentStatus':'Deployed','sharingModel':'Read'})

    def test_explicit_access_is_not_silently_changed(self):
        for text in ['Create a private Population object', 'Create Population object with public read/write sharing', 'Create Population object that only managers can see', 'Create Population object. Set sharingModel to ReadWrite.']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                apply_custom_object_defaults(plan({'sharingModel':'ReadWrite'}), text)

    def test_explicit_supported_setting(self):
        result = apply_custom_object_defaults(plan({'sharingModel':'Read'}), 'Create a Population custom object. Set sharingModel to Read.')
        self.assertTrue(validate_plan(result).valid)

    def test_config_rejected_during_planning(self):
        for config in [{'sharingModel':'ReadWrite'}, {'nameFieldType':'AutoNumber'}, {'deploymentStatus':'InDevelopment'}, {'unknown':True}, {'pluralLabel':''}, 'invalid']:
            with self.subTest(config=config):
                self.assertFalse(validate_plan(plan(config)).valid)

    def test_approved_plan_not_changed(self):
        source = plan({'sharingModel':'ReadWrite'});source['status']='APPROVED'
        before=deepcopy(source)
        with self.assertRaises(ValueError):
            apply_custom_object_defaults(source, 'Create a Population custom object')
        self.assertEqual(before,source)

    def test_update_not_changed(self):
        source=plan({'label':'Population Updated'});source['items'][0]['action']='UPDATE'
        self.assertEqual(source, apply_custom_object_defaults(source, 'Update Population label'))

    def test_complex_requirement_does_not_overwrite_nondefault(self):
        result=apply_custom_object_defaults(plan({'sharingModel':'ReadWrite'}), 'Create Population object and add a Date field')
        self.assertEqual(result['items'][0]['config']['sharingModel'],'ReadWrite')
        self.assertFalse(validate_plan(result).valid)

    def test_prompt_contains_policy_and_original_requirement(self):
        with patch('Backend.AI.app.prompts.prompt_builder.load_common_rules',return_value='Common'), patch('Backend.AI.app.prompts.prompt_builder.load_planning_prompt',return_value='{{requirement}} {{salesforce_context}}'):
            result=build_planning_prompt('Create Population object', {'objects':[]})
        self.assertIn('config.sharingModel = "Read"',result)
        self.assertIn('Create Population object',result)

    def test_service_normalizes_real_ai_response(self):
        provider=Mock();provider.generate.return_value=json.dumps(plan({'sharingModel':'ReadWrite'}))
        selector=Mock();selector.select.return_value={'objects':[]}
        with patch('Backend.AI.app.services.planning_service.build_planning_prompt',return_value='prompt'):
            result=PlanningService(provider,context_selector=selector).generate_plan('Create a Population custom object', {'objects':[]})
        self.assertEqual(result.items[0].config['sharingModel'],'Read')
        self.assertEqual(result.status,'DRAFT')


if __name__ == '__main__':
    unittest.main()
