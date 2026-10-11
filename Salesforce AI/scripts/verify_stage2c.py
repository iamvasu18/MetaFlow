"""Infrastructure smoke test: no Salesforce/model requests; inserts rolled back."""
import os
import uuid
from Backend.AI.app.account_api import SCHEMA
from Backend.AI.app.services.app_database import connect_postgres, postgres_enabled, raw_connection
from Backend.AI.app.services.job_notifications import client


def main():
    if not postgres_enabled() or not os.getenv('APP_REDIS_URL'):
        raise SystemExit('Configure APP_DATABASE_URL and APP_REDIS_URL first.')
    if not os.getenv('APP_ENCRYPTION_KEY'):
        raise SystemExit('Configure the existing encryption key for web and worker.')
    from cryptography.fernet import Fernet
    Fernet(os.environ['APP_ENCRYPTION_KEY'].encode())
    identifier = 'VERIFY-' + uuid.uuid4().hex
    class Rollback(Exception): pass
    try:
        with connect_postgres(SCHEMA) as connection:
            connection.execute('INSERT INTO users VALUES(?,?,?,?,?)', (identifier, identifier, 'Verify', 'unused', 'unused'))
            connection.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)', (identifier, 'Connected', 1.5, 'first'))
            connection.execute('INSERT OR REPLACE INTO org_health VALUES(?,?,?,?)', (identifier, 'Connected', 2.5, 'second'))
            assert connection.execute('SELECT message FROM org_health WHERE org_id=?', (identifier,)).fetchone()[0] == 'second'
            connection.execute('INSERT INTO monitor_jobs VALUES(?,?,?,?)', (identifier, identifier, identifier, 0))
            assert connection.execute('SELECT COUNT(*) FROM monitor_jobs WHERE plan_id=?', (identifier,)).fetchone()[0] == 1
            raise Rollback()
    except Rollback:
        pass
    first = raw_connection()
    second = raw_connection()
    first.autocommit = second.autocommit = True
    lock_key = int(uuid.uuid4().int % (2**63 - 1))
    try:
        first.execute('SELECT pg_advisory_lock(%s)', (lock_key,))
        assert not second.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (lock_key,)).fetchone()['acquired']
        first.execute('SELECT pg_advisory_unlock(%s)', (lock_key,))
        assert second.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (lock_key,)).fetchone()['acquired']
        second.execute('SELECT pg_advisory_unlock(%s)', (lock_key,))
    finally:
        first.close(); second.close()
    with client() as connection:
        assert connection.ping()
        key = 'metaflow:verify:' + identifier
        connection.lpush(key, 'wake')
        connection.expire(key, 10)
        assert connection.blpop(key, timeout=1)[1] == 'wake'
        connection.delete(key)
    print('Postgres transactions/upserts/shared locks/monitor queue and Redis wakeup passed. No Salesforce or AI calls.')


if __name__ == '__main__': main()
