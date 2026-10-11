"""Session locks protect web submissions and read-only worker polling."""
from contextlib import contextmanager
import hashlib
from threading import local
from Backend.AI.app.services.app_database import postgres_enabled, raw_connection

_held = local()


@contextmanager
def shared_plan_lock(plan_id, blocking=True):
    if not postgres_enabled() or not plan_id:
        yield True
        return
    held = getattr(_held, 'keys', set())
    if plan_id in held:
        yield True
        return
    key = int.from_bytes(hashlib.sha256(('metaflow-plan:' + plan_id).encode()).digest()[:8], 'big', signed=True)
    connection = raw_connection()
    connection.autocommit = True
    acquired = False
    try:
        # Bound blocking waits; failure stops the operation before a Salesforce call.
        connection.execute("SET lock_timeout = '15s'")
        if blocking:
            connection.execute('SELECT pg_advisory_lock(%s)', (key,))
            acquired = True
        else:
            row = connection.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (key,)).fetchone()
            acquired = row['acquired']
        if acquired:
            _held.keys = held | {plan_id}
        yield acquired
    finally:
        try:
            if acquired:
                _held.keys = held
                connection.execute('SELECT pg_advisory_unlock(%s)', (key,))
        finally:
            connection.close()
