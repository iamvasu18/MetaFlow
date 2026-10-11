import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from Backend.AI.app.account_api import SCHEMA
from Backend.AI.app.services.app_database import AppRow, schema_contract, translate
from Backend.AI.app.tests.test_workspace_regression import client, main, accounts, package


def test_schema_contract_and_upserts_preserve_composite_identity():
    tables = schema_contract(SCHEMA)
    assert tables['org_tokens'] == (['user_id','org_id','payload'], ['user_id','org_id'])
    sql = translate('INSERT OR REPLACE INTO org_tokens VALUES(?,?,?)', tables)
    assert 'ON CONFLICT (user_id,org_id) DO UPDATE SET payload=EXCLUDED.payload' in sql
    assert sql.count('%s') == 3
    assert translate('INSERT OR IGNORE INTO evaluation_events VALUES(?,?,?,?,?,?,?)', tables).endswith('DO NOTHING')
    assert 'attempts.count+1' in translate('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', tables)


def test_sql_literals_and_row_contract():
    assert translate("SELECT '?' AS text WHERE id=?", {}) == "SELECT '?' AS text WHERE id=%s"
    row = AppRow(id='a', count=2)
    assert row[0] == row['id'] == 'a'
    assert dict(row) == {'id':'a','count':2}
    with pytest.raises(ValueError): translate('INSERT OR REPLACE INTO unknown VALUES(?)', {})


def scoped_save(bundle):
    owner=accounts.current_account.set('u');org=accounts.current_org.set('app_ours')
    try: main.metadata_spec_store.save_package(bundle)
    finally: accounts.current_account.reset(owner);accounts.current_org.reset(org)


def test_queue_persists_and_terminal_state_retires_atomically(client):
    _, bundle = package(state='pending')
    scoped_save(bundle)
    with accounts.db() as connection:
        row = connection.execute('SELECT * FROM monitor_jobs WHERE plan_id=?',('PLAN-old',)).fetchone()
        assert row['user_id'] == 'u' and row['org_id'] == 'app_ours'
        assert connection.execute('SELECT payload FROM workspace_packages WHERE id=?',('PLAN-old',)).fetchone()
    bundle['state']='validated';scoped_save(bundle)
    with accounts.db() as connection:
        assert connection.execute('SELECT * FROM monitor_jobs WHERE plan_id=?',('PLAN-old',)).fetchone() is None


def test_external_scan_recovers_interrupted_job_without_resubmission(client, monkeypatch):
    from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
    monkeypatch.setenv('APP_JOB_MODE','external')
    _, bundle=package(state='running');scoped_save(bundle)
    with accounts.db() as connection:
        connection.execute('UPDATE monitor_jobs SET next_poll=0')
    with patch.object(main.default_pipeline,'deploy') as deploy, patch.object(main.default_pipeline,'report') as report:
        poll_saved_jobs()
    deploy.assert_not_called();report.assert_not_called()
    assert main.metadata_spec_store.get_package('PLAN-old')['state']=='unknown'
    with accounts.db() as connection:
        assert connection.execute('SELECT COUNT(*) FROM monitor_jobs').fetchone()[0]==0


def test_external_scan_ignores_jobs_not_yet_due(client, monkeypatch):
    from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
    monkeypatch.setenv('APP_JOB_MODE','external')
    _, bundle=package(state='pending');bundle['jobId']='known';scoped_save(bundle)
    with patch.object(main.default_pipeline,'report') as report: poll_saved_jobs()
    report.assert_not_called()


def test_shared_lock_is_reentrant_and_unlocks_on_failure(monkeypatch):
    from Backend.AI.app.services import shared_plan_lock as locks
    commands=[]
    class Connection:
        def execute(self,sql,params=()):
            commands.append(sql)
            return SimpleNamespace(fetchone=lambda:{'acquired':True})
        def close(self): commands.append('close')
    monkeypatch.setattr(locks,'postgres_enabled',lambda:True)
    monkeypatch.setattr(locks,'raw_connection',Connection)
    with pytest.raises(RuntimeError):
        with locks.shared_plan_lock('PLAN-test'):
            with locks.shared_plan_lock('PLAN-test'):
                raise RuntimeError('stopped')
    assert sum('pg_advisory_lock(' in sql for sql in commands)==1
    assert sum('pg_advisory_unlock(' in sql for sql in commands)==1
    assert commands[-1]=='close'


def test_busy_shared_lock_does_not_unlock_another_worker(monkeypatch):
    from Backend.AI.app.services import shared_plan_lock as locks
    commands=[]
    class Connection:
        def execute(self,sql,params=()):
            commands.append(sql)
            return SimpleNamespace(fetchone=lambda:{'acquired':False})
        def close(self): commands.append('close')
    monkeypatch.setattr(locks,'postgres_enabled',lambda:True)
    monkeypatch.setattr(locks,'raw_connection',Connection)
    with locks.shared_plan_lock('PLAN-busy',blocking=False) as acquired: assert not acquired
    assert not any('pg_advisory_unlock' in sql for sql in commands)


def test_redis_failure_does_not_undo_persisted_job(monkeypatch):
    from Backend.AI.app.services import job_notifications
    monkeypatch.setenv('APP_REDIS_URL','redis://localhost:6379/0')
    monkeypatch.setattr(job_notifications,'client',lambda:(_ for _ in ()).throw(OSError('unavailable')))
    job_notifications.notify()
    assert job_notifications.wait() is False


def test_copy_migration_preserves_source_and_rejects_nonempty_target(tmp_path, monkeypatch):
    import sqlite3
    from scripts import migrate_app_postgres as migration
    source = tmp_path / 'source.sqlite3'
    destination = tmp_path / 'destination.sqlite3'
    with sqlite3.connect(source) as connection:
        connection.executescript(SCHEMA)
        connection.execute('INSERT INTO users VALUES(?,?,?,?,?)', ('u','u@example.test','Test','salt','hash'))
    original = source.read_bytes()
    class Target:
        def __init__(self):
            self.inner = sqlite3.connect(destination)
            self.inner.executescript(SCHEMA)
            self.inner.row_factory = sqlite3.Row
            self.connection = SimpleNamespace(execute=lambda *a: None)
        def execute(self, sql, params=()): return self.inner.execute(sql, params)
        def __enter__(self): return self
        def __exit__(self, kind, *args):
            self.inner.rollback() if kind else self.inner.commit()
            self.inner.close()
    monkeypatch.setattr(migration,'postgres_enabled', lambda: True)
    monkeypatch.setattr(migration,'connect_postgres', lambda schema: Target())
    assert migration.migrate(source)['users'] == 1
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match='Destination must be empty'): migration.migrate(source)
    assert source.read_bytes() == original
