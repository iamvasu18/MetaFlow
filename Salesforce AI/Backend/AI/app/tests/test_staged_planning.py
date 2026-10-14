"""Safety and generality regression tests for token-budget staging."""
import pytest
from Backend.AI.app.services.staged_planning import (
    independent_requirements, merge_independent_plans, StagedPlanningUnavailable,
)
from Backend.AI.app.validators.plan_validator import ImplementationPlan


def test_independent_explicit_requirements():
    assert independent_requirements(
        '- Create a Case priority field\n- Create an unrelated Account category field'
    ) == ['Create a Case priority field', 'Create an unrelated Account category field']


@pytest.mark.parametrize('requirement', [
    'Build a complex onboarding system with Flow, Apex and LWC',
    '- Create an Account object\n- Add those fields to it',
    'Create a system:\n- Create a field\n- Create a Flow',
    '- Create a field\n- Create a field',
])
def test_ambiguous_decomposition_fails_closed(requirement):
    with pytest.raises(StagedPlanningUnavailable):
        independent_requirements(requirement)


def plan(name, *, dependency=(), approval='PENDING'):
    return ImplementationPlan.model_validate({
        'id': 'p', 'requirementId': 'r', 'summary': f'Create {name}',
        'status': 'DRAFT',
        'items': [{'id': 'ITEM-1', 'action': 'CREATE',
                   'metadataType': 'CustomField', 'fullName': name,
                   'dependencies': list(dependency), 'approval': approval,
                   'deployment': None, 'config': {'type':'Text'}}],
    })


def test_stage_merge_preserves_configs_and_rekeys_ids():
    merged = merge_independent_plans([
        plan('Account.Region__c'), plan('Case.Source_Detail__c')
    ])
    assert [item['id'] for item in merged['items']] == ['STAGE1_ITEM-1', 'STAGE2_ITEM-1']
    assert merged['items'][0]['config'] == {'type':'Text'}
    assert merged['status'] == 'DRAFT'


def test_stage_merge_rejects_component_collision():
    with pytest.raises(StagedPlanningUnavailable):
        merge_independent_plans([plan('Account.Region__c'), plan('Account.Region__c')])


def test_stage_merge_rejects_approval():
    with pytest.raises(StagedPlanningUnavailable):
        merge_independent_plans([plan('Account.Region__c', approval='APPROVED'), plan('Case.Detail__c')])


def test_stage_merge_rejects_cross_stage_dependencies():
    with pytest.raises(StagedPlanningUnavailable):
        merge_independent_plans([plan('Account.Region__c', dependency=('other',)), plan('Case.Detail__c')])


def test_provider_output_limit_uses_staged_fallback_only_after_compact_retry(monkeypatch):
    from Backend.AI.app.services.planning_service import PlanningService
    from Backend.AI.app.providers.errors import AIOutputLimitError

    class TokenLimitProvider:
        calls = 0
        def generate(self, system_prompt, user_prompt):
            self.calls += 1
            raise AIOutputLimitError('max_tokens')

    provider = TokenLimitProvider()
    service = PlanningService(provider=provider)
    sentinel = object()
    stage_calls = []

    def fake_stage(requirement, context):
        stage_calls.append((requirement, context))
        return sentinel

    monkeypatch.setattr(service, '_generate_staged_plan', fake_stage)
    result = service.generate_plan('- Create an Account field\n- Create a Case field', {'objects': []})
    assert result is sentinel
    assert provider.calls == 2
    assert len(stage_calls) == 1


def test_token_fallback_fails_closed_for_undividable_requirement():
    from Backend.AI.app.services.planning_service import PlanningService
    service = PlanningService(provider=object())
    with pytest.raises(RuntimeError, match='No plan was saved'):
        service._generate_staged_plan('Build a complex LWC and Apex integration', {'objects': []})
