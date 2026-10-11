"""Versioned planning eval; replay by default, explicit --mode model for paid generation.
No Salesforce connection, validation job, approval or deployment is performed.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from Backend.AI.app.services.discovery_service import check_requested_components, ComponentConflict
from Backend.AI.app.services.planning_service import PlanningService
from Backend.AI.app.services.metadata_safety import validate_component_name
from Backend.AI.app.services.evaluation_service import usage_cost


class EvalProvider:
    def __init__(self, replay, provider=None):
        self.replay, self.provider = replay, provider
        self.calls = []

    def generate(self, system_prompt, user_prompt):
        self.calls.append(hashlib.sha256((system_prompt+'\n'+user_prompt).encode()).hexdigest())
        if self.provider:
            return self.provider.generate(system_prompt, user_prompt)
        return json.dumps(self.replay)


def run_case(case, context, provider=None):
    measured = EvalProvider(case['replay'], provider if case['category']=='behavior' else None)
    start = time.perf_counter()
    outcome, plan, error = 'plan', None, None
    before = len(provider.usage_events) if provider else 0
    before_attempts = provider.generation_attempts if provider else 0
    try:
        check_requested_components(case['requirement'], deepcopy(context))
        plan = PlanningService(measured).generate_plan(case['requirement'], salesforce_context=deepcopy(context))
        for item in plan.items:
            validate_component_name(item.metadataType,item.fullName)
    except ComponentConflict:
        outcome = 'clarification'
    except (ValueError, RuntimeError) as exc:
        outcome, error = 'rejected', str(exc)[:500]
    except Exception as exc:
        outcome, error = 'provider-error', type(exc).__name__
    passed = outcome == case['expect']['outcome']
    if passed and outcome == 'plan':
        actual = {(i.metadataType,i.fullName) for i in plan.items if i.action != 'NO_CHANGE'}
        expected = {tuple(pair) for pair in case['expect']['components']}
        passed = actual == expected
        for key,value in case['expect'].get('config',{}).items():
            passed = passed and plan.items[0].config.get(key) == value
        if case['id'] == 'leave-number-stays-number':
            c = next(i.config for i in plan.items if i.metadataType == 'Flow')
            passed = passed and not c.get('formulas') and any(
                e['expression'].replace(' ','') == '{!$Record.End_Date__c}-{!$Record.Start_Date__c}+1'
                for e in c.get('expressions',[]))
    usage = provider.usage_events[before:] if provider else []
    if provider and provider.generation_attempts-before_attempts > len(usage):
        usage = [*usage,None]
    return {'caseId':case['id'],'category':case['category'],'passed':bool(passed),'outcome':outcome,
        'seconds':round(time.perf_counter()-start,3),'plannerCalls':len(measured.calls),
        'promptHashes':measured.calls,'usage':usage,'costUsd':usage_cost(usage),'error':error}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['replay','model'],default='replay')
    parser.add_argument('--corpus',default=str(Path(__file__).with_name('stage1-v1.json')))
    parser.add_argument('--output',default='evaluation-results.json')
    args=parser.parse_args()
    corpus_bytes=Path(args.corpus).read_bytes(); corpus=json.loads(corpus_bytes)
    provider=None
    if args.mode=='model':
        from Backend.AI.app.providers.ai_provider import AnthropicProvider
        provider=AnthropicProvider()
    rows=[run_case(case,corpus['context'],provider) for case in corpus['cases']]
    report={'schemaVersion':1,'mode':args.mode,'corpusHash':hashlib.sha256(corpus_bytes).hexdigest(),
        'contextVersion':corpus['contextVersion'],'model':provider.model if provider else 'golden-replay',
        'passed':sum(r['passed'] for r in rows),'total':len(rows),'cases':rows,
        'liveSalesforceValidation':'not run','userAcceptance':'not measured by fixtures'}
    Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"{report['passed']}/{report['total']} evaluation cases passed ({args.mode}).")
    raise SystemExit(0 if report['passed']==report['total'] else 1)


if __name__=='__main__': main()
