"""Isolate unit tests from local application configuration and data."""
import os
import tempfile
from pathlib import Path

_test_directory = tempfile.TemporaryDirectory(
    prefix="metaflow-tests-",
    ignore_cleanup_errors=True,
)

os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1",
    "APP_DATABASE_URL": "",
    "APP_DATABASE": str(
        Path(_test_directory.name) / "accounts.sqlite3"
    ),
    "APP_REDIS_URL": "",
    "APP_JOB_MODE": "embedded",
    "APP_BACKGROUND_JOBS": "false",
})


def pytest_sessionfinish(session, exitstatus):
    _test_directory.cleanup()