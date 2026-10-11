"""Observed workflow metrics. Never infer user acceptance or live validation from fixtures."""
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import logging
import math
import os
import statistics
import time
from uuid import uuid4


evaluation_plan = ContextVar('evaluation_plan', default=None)


def plan_measurement(fn):
    @wraps(fn)
    def wrapped(plan_id, *args, **kwargs):
        token = evaluation_plan.set(plan_id)
        try:
            return fn(plan_id, *args, **kwargs)
        finally:
            evaluation_plan.reset(token)
    return wrapped


def usage_cost(records):
    """Rates are explicit USD/million tokens, per model, never guessed."""
    if not records or any(r is None for r in records):
        return None
    try:
        rates = json.loads(os.getenv("AI_PRICING_JSON", "{}"))
        total = 0.0
        for record in records:
            model_rates = rates.get(record["model"], {})
            for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                count = record.get(key, 0)
                if not isinstance(count, int) or count < 0:
                    return None
                if count:
                    rate = model_rates.get(key)
                    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 0:
                        return None
                    total += count * rate / 1_000_000
        return round(total, 8)
    except (ValueError, TypeError, KeyError):
        return None


def record_event(kind, payload, plan_id=None, identity=None):
    from Backend.AI.app.account_api import current_account, current_org, db
    owner, org = current_account.get(), current_org.get()
    if not owner or not org:
        return
    event_id = hashlib.sha256(json.dumps([owner, org, plan_id, kind, identity], sort_keys=True).encode()).hexdigest() if identity else str(uuid4())
    with db() as c:
        c.execute("INSERT OR IGNORE INTO evaluation_events VALUES(?,?,?,?,?,?,?)",
            (event_id, owner, org, plan_id, kind, json.dumps(payload), time.time()))


def observe_package(package):
    """Immutable events, deduplicated across saves/polls/restarts."""
    plan_id = package['plan']['id']
    perf = package.get('performance', {})
    generation = perf.get('generationId')
    if generation and package.get("layoutReady") and package.get("evaluationOriginPlanId", plan_id) == plan_id:
        record_event('draft', {'generationId': generation, 'sourceHash': package['sourceHash']}, plan_id, generation)
    approved = package.get('approvedHash')
    if approved:
        record_event('approval', {'sourceHash': approved}, plan_id, approved)
    started = package.get('operationStartedAt')
    if started and package.get('operation') == 'validate':
        record_event('validation_start', {'startedAt': started}, plan_id, str(started))
        if package.get('state') in {'validated', 'failed'}:
            record_event('validation_result', {'startedAt': started, 'passed': package['state'] == 'validated',
                'seconds': package.get('operationSeconds')}, plan_id, str(started))


def safe_observe_package(package):
    try:
        observe_package(package)
    except Exception:
        logging.getLogger(__name__).exception('Evaluation package event could not be recorded')


def summary(owner, org=None):
    from Backend.AI.app.account_api import db
    query = 'SELECT * FROM evaluation_events WHERE user_id=?'
    args = [owner]
    if org:
        query += ' AND org_id=?'
        args.append(org)
    with db() as c:
        rows = c.execute(query + ' ORDER BY created,id', args).fetchall()
    drafts, approvals, starts, results, attempts, attempt_plans, ready_times = {}, {}, {}, {}, {}, {}, {}
    for row in rows:
        data = json.loads(row['payload']); plan = row['plan_id']; kind = row['kind']
        if kind == 'generation':
            attempts[data['generationId']] = data
            if plan: attempt_plans[data['generationId']] = plan
        elif kind == 'draft_ready': ready_times[data['generationId']] = data['totalSeconds']
        elif kind == 'draft':
            drafts.setdefault(plan, data)
            attempt_plans[data['generationId']] = plan
        elif kind == 'approval': approvals.setdefault(plan, data)
        elif kind == 'validation_start': starts.setdefault(plan, []).append(data['startedAt'])
        elif kind == 'validation_result': results[(plan, data['startedAt'])] = data
    accepted = sum(approvals[p]['sourceHash'] == d['sourceHash'] for p,d in drafts.items() if p in approvals)
    first = [results[(p,min(values))] for p,values in starts.items() if (p,min(values)) in results]
    all_attempts = list(attempts.values())
    costs = [a['costUsd'] for a in all_attempts if a.get('costUsd') is not None]
    times = [a['totalSeconds'] for a in all_attempts]
    per_plan = {plan: [a for generation,a in attempts.items() if attempt_plans.get(generation)==plan] for plan in drafts}
    saved_times = [sum(ready_times.get(a['generationId'],a['totalSeconds']) for a in values) for values in per_plan.values() if values]
    saved_costs = [sum(a['costUsd'] for a in values) for values in per_plan.values() if values and all(a.get('costUsd') is not None for a in values)]
    def metric(n,d): return {'numerator': n, 'denominator': d, 'rate': n/d if d else None}
    return {'schemaVersion': 1,
        'acceptanceWithoutEdits': metric(accepted,len(drafts)),
        'firstTryValidation': metric(sum(r['passed'] for r in first),len(first)),
        'generationAttempts': len(all_attempts), 'generatedPlans': len(drafts),
        'approvedPlans': sum(p in drafts for p in approvals), 'pendingFirstValidations': len(starts)-len(first),
        'meanSecondsPerSavedPlan': statistics.mean(saved_times) if saved_times else None,
        'meanSecondsPerGenerationAttempt': statistics.mean(times) if times else None,
        'meanKnownCostUsdPerSavedPlan': statistics.mean(saved_costs) if saved_costs else None,
        'savedPlansWithKnownCost': len(saved_costs),
        'meanKnownCostUsdPerAttempt': statistics.mean(costs) if costs else None,
        'knownCostAttempts': len(costs), 'totalKnownCostUsd': sum(costs) if costs else None,
        'definitions': 'Acceptance: first saved source hash equals first approved hash, divided by all generated plans; unapproved plans remain in the denominator. First validation: first submitted validation with a terminal result; pending/unknown excluded. Saved-plan time includes review preparation when a draft-ready event is available and associated repair attempts; cost includes associated model usage; operation wait times are separate. Failed initial attempts have no saved plan and appear in attempt totals. Missing usage/pricing is unknown, never zero. Repairs sharing a plan ID do not erase its original baseline.'}
