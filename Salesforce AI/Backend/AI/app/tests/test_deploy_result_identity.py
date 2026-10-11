from unittest.mock import patch
import pytest
from Backend.AI.app.tests.test_workspace_regression import client, main, package


@pytest.mark.parametrize('check_only', [True, None, 'false'])
def test_check_only_or_unconfirmed_result_never_becomes_deployed(client, check_only):
    _, bundle = package()
    payload = {'result': {'id': 'validation-job', 'done': True, 'success': True,
                          'checkOnly': check_only, 'status': 'Succeeded'}}
    with patch.object(main.default_pipeline, 'check_tests'), patch('Backend.AI.app.services.planning_performance.invalidate_org_context') as invalidate:
        result = main.save_default_result('PLAN-old', bundle, payload, 'deploy')
    assert result['state'] == 'unknown'
    assert 'not confirmed' in result['error']
    invalidate.assert_not_called()


def test_real_commit_can_be_confirmed(client):
    _, bundle = package()
    payload = {'result': {'id': 'deployment-job', 'done': True, 'success': True, 'checkOnly': False}}
    with patch.object(main.default_pipeline, 'check_tests'), patch('Backend.AI.app.services.planning_performance.invalidate_org_context') as invalidate:
        result = main.save_default_result('PLAN-old', bundle, payload, 'deploy')
    assert result['state'] == 'deployed'
    invalidate.assert_called_once()


def test_validation_stays_validation(client):
    _, bundle = package()
    payload = {'result': {'id': 'validation-job', 'done': True, 'success': True, 'checkOnly': True}}
    with patch.object(main.default_pipeline, 'check_tests'):
        result = main.save_default_result('PLAN-old', bundle, payload, 'validate')
    assert result['state'] == 'validated'
    assert result['validatedHash'] == bundle['sourceHash']
