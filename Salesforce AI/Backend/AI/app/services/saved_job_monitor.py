"""Track saved validation/deploy jobs for the single-process application."""
import json
import logging
import os
import time


def poll_saved_jobs():
    from Backend.AI.app import main
    from Backend.AI.app.account_api import db,current_account,current_org,record_workflow_response
    with db() as c:
        if os.getenv('APP_JOB_MODE') == 'external':
            rows=c.execute('SELECT w.id,w.user_id,w.org_id,w.payload FROM workspace_packages w JOIN orgs o ON o.id=w.org_id AND o.user_id=w.user_id JOIN monitor_jobs j ON j.plan_id=w.id AND j.user_id=w.user_id AND j.org_id=w.org_id WHERE j.next_poll<=? ORDER BY j.next_poll LIMIT 100', (time.time(),)).fetchall()
        else:
            rows=c.execute('SELECT w.id,w.user_id,w.org_id,w.payload FROM workspace_packages w JOIN orgs o ON o.id=w.org_id AND o.user_id=w.user_id').fetchall()
    for row in rows:
        try:
            saved=json.loads(row['payload'])['package']
            if saved.get('state') not in {'pending','unknown','running'}:continue
            account=current_account.set(row['user_id']);org=current_org.set(row['org_id'])
            try:
                # All submission/mutation paths share this lock. A running state
                # after obtaining it means no submitting worker is still active.
                with main.layout_workflow.try_plan_lock(row['id']) as acquired:
                    if not acquired:
                        continue
                    main.restore_workspace_package(row['id'],row['user_id'],row['org_id'])
                    package=main.metadata_spec_store.get_package(row['id'])
                    if not package:
                        continue
                    if package.get('state') == 'running':
                        package.update(state='unknown', validatedHash=None,
                            error='Submission was interrupted; its Salesforce outcome is not confirmed.',
                            nextAction='Inspect the saved job or Salesforce Deployment Status before retrying. No operation was resubmitted.')
                        main.metadata_spec_store.save_package(package)
                    if package.get('state') not in {'pending','unknown'} or not package.get('jobId'):
                        with db() as c:c.execute('DELETE FROM monitor_jobs WHERE plan_id=? AND user_id=? AND org_id=?',(row['id'],row['user_id'],row['org_id']))
                        continue
                    with db() as c:c.execute('UPDATE monitor_jobs SET next_poll=? WHERE plan_id=?',(time.time()+5,row['id']))
                    result=main.report_default_package(row['id'])
                    record_workflow_response({'id':row['user_id']},row['org_id'],row['id'],
                        '/api/plans/'+row['id']+'/report',result,200)
            finally:
                current_account.reset(account);current_org.reset(org)
        except Exception:
            logging.getLogger(__name__).exception('Unable to refresh saved Salesforce job %s',row['id'])


def monitor_saved_jobs(stop):
    # Wait before the first pass so application initialization can finish.
    while not stop.wait(5):
        try:poll_saved_jobs()
        except Exception:logging.getLogger(__name__).exception('Saved job monitor pass failed')
