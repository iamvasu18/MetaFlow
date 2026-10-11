"""Bounded planning-only context reuse. Deployment preflight remains live."""
from contextlib import contextmanager
from collections import OrderedDict
from functools import wraps
import hashlib
import json
import logging
from threading import RLock
from time import monotonic, perf_counter


class PlanningCache:
    def __init__(self, ttl=600, max_entries=32, max_bytes=16 * 1024 * 1024):
        self.ttl, self.max_entries, self.max_bytes = ttl, max_entries, max_bytes
        self.entries = OrderedDict()
        self.bytes = 0
        self.epoch = 0
        self.lock = RLock()

    def _remove(self, key):
        _, data = self.entries.pop(key)
        self.bytes -= len(data)

    def get(self, key):
        with self.lock:
            now = monotonic()
            for old in list(self.entries):
                if self.entries[old][0] <= now:
                    self._remove(old)
            entry = self.entries.get(key)
            if entry is None:
                return None, self.epoch
            self.entries.move_to_end(key)
            return json.loads(entry[1]), self.epoch

    def put(self, key, value, epoch):
        data = json.dumps(value, separators=(',', ':')).encode('utf-8')
        with self.lock:
            if epoch != self.epoch or len(data) > self.max_bytes:
                return
            if key in self.entries:
                self._remove(key)
            while self.entries and (len(self.entries) >= self.max_entries
                                    or self.bytes + len(data) > self.max_bytes):
                self._remove(next(iter(self.entries)))
            self.entries[key] = (monotonic() + self.ttl, data)
            self.bytes += len(data)

    def invalidate(self, owner, org):
        with self.lock:
            self.epoch += 1  # In-flight older discoveries must not refill the cache.
            for key in list(self.entries):
                if key[:2] == (owner, org):
                    self._remove(key)


planning_cache = PlanningCache()


def invalidate_org_context(owner, org):
    """Invalidate planning and overview snapshots without waiting for network reads."""
    planning_cache.invalidate(owner, org)
    if owner and org:
        from Backend.AI.app.account_api import db
        with db() as c:
            c.execute('INSERT INTO org_cache_epochs VALUES(?,?,1) ON CONFLICT(user_id,org_id) DO UPDATE SET epoch=epoch+1', (owner, org))
            c.execute('DELETE FROM org_intelligence_cache WHERE user_id=? AND org_id=?', (owner, org))



class TimedProvider:
    def __init__(self, provider):
        self.provider = provider
        self.seconds = 0
        self.calls = 0
        self.usage = []
        self.prompt_hashes = []

    def generate(self, *args, **kwargs):
        start = perf_counter()
        self.calls += 1
        system = kwargs.get("system_prompt", args[0] if args else "")
        user = kwargs.get("user_prompt", args[1] if len(args)>1 else "")
        self.prompt_hashes.append(hashlib.sha256((str(system)+"\n"+str(user)).encode()).hexdigest())
        underlying = self.provider
        seen = set()
        while 'provider' in vars(underlying) and id(underlying) not in seen:
            seen.add(id(underlying))
            underlying = underlying.provider
        events = vars(underlying).get('usage_events')
        before = len(events) if isinstance(events, list) else None
        before_attempts = vars(underlying).get("generation_attempts", 0)
        try:
            return self.provider.generate(*args, **kwargs)
        finally:
            self.seconds += perf_counter() - start
            if before is not None:
                # Repair adapters may replay pinned JSON without another model call.
                self.usage.extend(events[before:])
                if not events[before:] and vars(underlying).get("generation_attempts", 0) > before_attempts:
                    self.usage.append(None)
            else:
                self.usage.append(None)


def timed_generation(method):
    @wraps(method)
    def wrapped(self, request, provider):
        from uuid import uuid4
        from Backend.AI.app.services.evaluation_service import record_event, usage_cost, evaluation_plan
        start = perf_counter()
        measured = TimedProvider(provider)
        generation_id = str(uuid4())
        outcome = 'failed'
        result = None
        try:
            result = method(self, request, measured)
            outcome = 'generated'
            return result
        finally:
            metrics = {
                'generationId': generation_id, 'outcome': outcome,
                'totalSeconds': round(perf_counter() - start, 3),
                'aiSeconds': round(measured.seconds, 3), 'aiCalls': measured.calls,
                'promptHashes': measured.prompt_hashes, 'usage': measured.usage, 'costUsd': usage_cost(measured.usage),
            }
            if result is not None:
                result['performance'] = metrics
            try:
                record_event('generation', metrics, plan_id=evaluation_plan.get() or (result.get('plan', {}).get('id') if result else None), identity=generation_id)
            except Exception:
                logging.getLogger(__name__).exception('Generation metrics could not be recorded')
            logging.getLogger(__name__).warning(
                'Planning total_seconds=%.3f ai_seconds=%.3f ai_calls=%d',
                perf_counter() - start, measured.seconds, measured.calls,
            )
    return wrapped


@contextmanager
def measured_repair(provider, plan_id):
    """Include source-specific repair cost/time even when the repair is rejected."""
    from uuid import uuid4
    from Backend.AI.app.services.evaluation_service import record_event, usage_cost
    measured = TimedProvider(provider)
    start = perf_counter()
    outcome = 'failed'
    try:
        yield measured
        outcome = 'repaired'
    finally:
        generation_id = str(uuid4())
        metrics = {'generationId': generation_id, 'outcome': outcome,
            'totalSeconds': round(perf_counter()-start,3), 'aiSeconds': round(measured.seconds,3),
            'aiCalls': measured.calls, 'promptHashes': measured.prompt_hashes, 'usage': measured.usage, 'costUsd': usage_cost(measured.usage)}
        try:
            record_event('generation', metrics, plan_id=plan_id, identity=generation_id)
        except Exception:
            logging.getLogger(__name__).exception('Repair metrics could not be recorded')
