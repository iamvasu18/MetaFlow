"""Run with python -m Backend.AI.app.job_worker from Salesforce AI."""
import logging
import os
import signal
from threading import Event, Thread
from Backend.AI.app import account_api
from Backend.AI.app.services.app_database import postgres_enabled
from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
from Backend.AI.app.services.job_notifications import wait


def main():
    if not postgres_enabled() or os.getenv('APP_JOB_MODE') != 'external':
        raise SystemExit('External worker requires APP_DATABASE_URL and APP_JOB_MODE=external.')
    if not os.getenv('APP_ENCRYPTION_KEY'):
        raise SystemExit('Set the same APP_ENCRYPTION_KEY in the web server and worker.')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    stop = Event()
    for name in ('SIGINT', 'SIGTERM'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    logging.info('Durable Salesforce monitoring worker started')
    # Independent polling continues while generation/submission occupies this worker.
    def monitor():
        while not stop.is_set():
            try: poll_saved_jobs()
            except Exception: logging.exception('Durable Salesforce monitor scan failed')
            stop.wait(5)
    monitor_thread=Thread(target=monitor,daemon=True,name='durable-salesforce-monitor')
    monitor_thread.start()
    from Backend.AI.app.services.background_jobs import process_jobs
    logging.info('Durable background operation worker started')
    while not stop.is_set():
        try:
            process_jobs(stop=stop)
        except Exception:
            logging.exception('Durable background operation scan failed')
        if not stop.is_set() and not wait():
            stop.wait(5)
    monitor_thread.join(timeout=6)


if __name__ == '__main__':
    main()
