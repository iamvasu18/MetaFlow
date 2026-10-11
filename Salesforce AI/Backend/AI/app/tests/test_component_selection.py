from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import pytest
from Backend.AI.app.services.component_selection_service import select_components
from Backend.AI.app.services.metadata_service import DefaultMetadataPipeline
from Backend.AI.app.services.page_layout_service import PageLayoutService, Q, PROFILE_PATH, write_xml
from Backend.AI.app.tests.test_workspace_regression import client, accounts, main
import xml.etree.ElementTree as ET


def package():
    items = [
        {'id': 'object', 'metadataType': 'CustomObject', 'fullName': 'Leave__c', 'action': 'CREATE'},
        {'id': 'days', 'metadataType': 'CustomField', 'fullName': 'Leave__c.Days__c', 'action': 'CREATE'},
        {'id': 'reason', 'metadataType': 'CustomField', 'fullName': 'Leave__c.Reason__c', 'action': 'CREATE'},
        {'id': 'flow', 'metadataType': 'Flow', 'fullName': 'Calculate', 'action': 'CREATE', 'dependencies': ['days']},
    ]
    root = 'force-app/main/default/'
    files = {root + 'objects/Leave__c/Leave__c.object-meta.xml': '<CustomObject/>', root + 'objects/Leave__c/fields/Days__c.field-meta.xml': '<CustomField/>', root + 'objects/Leave__c/fields/Reason__c.field-meta.xml': '<CustomField/>', root + 'flows/Calculate.flow-meta.xml': '<Flow>Leave__c Days__c</Flow>'}
    result = dict(plan={'id': 'original', 'items': items}, files=files, baseFiles=deepcopy(files), components=[{'metadataType': i['metadataType'], 'fullName': i['fullName']} for i in items], targetOrg='app_ours', apiVersion='65.0', metadataSpecification={'metadata': [{'itemId': i['id']} for i in items]}, testClasses=[], layoutSelections={}, approvedHash='old', validatedHash='old', state='validated')
    result['sourceHash'] = DefaultMetadataPipeline.fingerprint(result)
    return result


def test_selection_keeps_dependencies_and_removes_unrelated_source():
    original = package()
    updated = select_components(original, ['Flow:Calculate'], original['sourceHash'], DefaultMetadataPipeline.fingerprint)
    assert {i['id'] for i in updated['plan']['items']} == {'flow', 'days', 'object'}
    assert not any('Reason__c' in p for p in updated['files'])
    assert updated['approvedHash'] is None and updated['validatedHash'] is None
    assert set(updated['selectionAddedDependencies']) == {'Leave__c', 'Leave__c.Days__c'}
    assert original['state'] == 'validated' and len(original['components']) == 4
    assert DefaultMetadataPipeline.fingerprint(updated) == updated['sourceHash']


@pytest.mark.parametrize('selected,hash_value', [([], None), (['Flow:Missing'], None), (['Flow:Calculate'], '0'*64)])
def test_invalid_or_stale_selection_is_rejected(selected, hash_value):
    original = package()
    with pytest.raises(ValueError):
        select_components(original, selected, hash_value or original['sourceHash'], DefaultMetadataPipeline.fingerprint)


def test_selection_endpoint_creates_owned_draft_and_preserves_original(client):
    original = client.get('/api/plans/PLAN-old').json()
    response = client.post('/api/plans/PLAN-old/selection', json={'source_hash': original['sourceHash'], 'components': ['CustomField:Metaflow__c.UI_Description__c']})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['id'] != 'PLAN-old' and result['plan']['status'] == 'DRAFT'
    assert not result.get('approvedHash') and not result.get('validatedHash')
    assert client.get('/api/plans/PLAN-old').json()['sourceHash'] == original['sourceHash']
    with accounts.db() as connection:
        assert connection.execute('SELECT user_id FROM plans WHERE id=?', (result['id'],)).fetchone()[0] == 'u'


def test_layout_manifest_retrieves_only_affected_object(tmp_path):
    (tmp_path / 'sfdx-project.json').write_text('{"sourceApiVersion":"65.0"}')
    def cli(root, args):
        if args[:3] == ['org', 'list', 'metadata']:
            return [{'fullName': name} for name in (['Account-Main', 'Contact-Main'] if args[-1] == 'Layout' else ['Account.Business', 'Contact.Business'])]
        write_xml(ET.Element(Q('Profile')), root / PROFILE_PATH)
        return {'success': True, 'done': True}
    service = PageLayoutService(tmp_path, 'app_ours')
    with patch.object(service, '_cli', side_effect=cli):
        _, names = service._retrieve(tmp_path, objects={'Account'})
    assert names == {'Account-Main'}
    manifest = (tmp_path / 'layout-retrieve.xml').read_text()
    assert 'Account.Business' in manifest and 'Contact' not in manifest
