"""Postgres queue contract smoke test. Test rows are rolled back, never executed."""
import json
import os
import time
from uuid import uuid4
from Backend.AI.app.account_api import SCHEMA
from Backend.AI.app.services.app_database import connect_postgres, postgres_enabled
from cryptography.fernet import Fernet


def main():
    if not postgres_enabled() or os.getenv('APP_JOB_MODE')!='external' or os.getenv('APP_BACKGROUND_JOBS','false').lower()!='true':
        raise SystemExit('Set APP_DATABASE_URL, APP_JOB_MODE=external and APP_BACKGROUND_JOBS=true.')
    Fernet(os.environ['APP_ENCRYPTION_KEY'].encode())
    class Rollback(Exception): pass
    identifier='VERIFY-'+uuid4().hex
    now=time.time()
    try:
        with connect_postgres(SCHEMA) as connection:
            sql='INSERT INTO background_jobs VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,org_id,request_key) DO NOTHING'
            values=(identifier,identifier,identifier,'generate','queued',json.dumps({'request':{'requirement':'verification only'}}),None,now,now,identifier)
            assert connection.execute(sql,values).rowcount==1
            duplicate=('OTHER-'+identifier,*values[1:])
            assert connection.execute(sql,duplicate).rowcount==0
            assert connection.execute("UPDATE background_jobs SET state='running' WHERE id=? AND state='queued'",(identifier,)).rowcount==1
            assert connection.execute("UPDATE background_jobs SET state='running' WHERE id=? AND state='queued'",(identifier,)).rowcount==0
            assert connection.execute('SELECT state FROM background_jobs WHERE id=?',(identifier,)).fetchone()[0]=='running'
            raise Rollback()
    except Rollback:
        pass
    with connect_postgres(SCHEMA) as connection:
        assert connection.execute('SELECT COUNT(*) FROM background_jobs WHERE id=?',(identifier,)).fetchone()[0]==0
    print('Background queue schema, idempotency and atomic claiming passed. Test rows rolled back; no AI or Salesforce calls.')


if __name__=='__main__': main()
