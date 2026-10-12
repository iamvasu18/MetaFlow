"""Run with python -m Backend.AI.app.job_worker from Salesforce AI."""

import logging
import os
import signal
from threading import Event, Thread

from Backend.AI.app import account_api
from Backend.AI.app.services.app_database import postgres_enabled
from Backend.AI.app.services.saved_job_monitor import poll_saved_jobs
from Backend.AI.app.services.job_notifications import wait
from Backend.AI.app.services.observability import (
    configure_logging,
    log_event,
)


logger = logging.getLogger(__name__)


def main():
    if not postgres_enabled() or os.getenv("APP_JOB_MODE") != "external":
        raise SystemExit(
            "External worker requires APP_DATABASE_URL "
            "and APP_JOB_MODE=external."
        )

    if not os.getenv("APP_ENCRYPTION_KEY"):
        raise SystemExit(
            "Set the same APP_ENCRYPTION_KEY in the web server and worker."
        )

    configure_logging()
    stop = Event()

    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())

    log_event(logger, "monitor_worker_started")

    # Monitoring continues while generation or submission occupies the worker.
    def monitor():
        while not stop.is_set():
            try:
                poll_saved_jobs()
            except Exception as error:
                log_event(
                    logger,
                    "monitor_scan_failed",
                    level=logging.ERROR,
                    error_type=type(error).__name__,
                )
            stop.wait(5)

    monitor_thread = Thread(
        target=monitor,
        daemon=True,
        name="durable-salesforce-monitor",
    )
    monitor_thread.start()

    from Backend.AI.app.services.background_jobs import process_jobs

    log_event(logger, "background_worker_started")

    try:
        while not stop.is_set():
            try:
                process_jobs(stop=stop)
            except Exception as error:
                log_event(
                    logger,
                    "background_scan_failed",
                    level=logging.ERROR,
                    error_type=type(error).__name__,
                )

            if not stop.is_set() and not wait():
                stop.wait(5)
    finally:
        stop.set()
        monitor_thread.join(timeout=6)
        log_event(logger, "worker_stopped")


if __name__ == "__main__":
    main()