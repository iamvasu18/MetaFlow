import json
from copy import deepcopy
import pytest
from Backend.AI.app.services.component_source_service import repair_sources

PATH = 'force-app/main/default/lwc/example/example.js'

def package():
    return {
        'sourceHash': 'a' * 64, 'requirement': 'Show an example',
        'components': [{'metadataType': 'LightningComponentBundle', 'fullName': 'example'}],
        'files': {PATH: 'original'}, 'baseFiles': {PATH: 'original'},
        'state': 'failed', 'lastResult': {'error': 'Compiler error'},
    }

def test_malformed_reply_retries_without_growing_previous_response():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            data = json.loads(kwargs['user_prompt'])
            assert data['files'][PATH] == 'original'
            assert 'previousResponse' not in data
            if self.calls == 1:
                return '```json\n{"files":'
            assert 'repairFeedback' in data
            return json.dumps({'files': {PATH: 'corrected'}})
    provider = Provider()
    assert repair_sources(original, 'example', '', provider) == {PATH: 'corrected'}
    assert provider.calls == 2
    assert original == before

def test_repeated_bad_replies_stop_after_three_calls_and_preserve_source():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            return 'invalid JSON'
    provider = Provider()
    with pytest.raises(ValueError, match='after 3 attempts'):
        repair_sources(original, 'example', '', provider)
    assert provider.calls == 3
    assert original == before

def test_out_of_scope_files_are_never_accepted():
    original = package()
    before = deepcopy(original)
    class Provider:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            return json.dumps({'files': {'force-app/main/default/classes/Other.cls': 'overwrite'}})
    provider = Provider()
    with pytest.raises(ValueError, match='allowed file paths'):
        repair_sources(original, 'example', '', provider)
    assert provider.calls == 3
    assert original == before
