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

import pytest

@pytest.fixture(autouse=True)
def authenticated_legacy_flow_tests(request, monkeypatch, tmp_path):
    """Legacy Flow route tests opt in explicitly and retain real account middleware.

    Current unified source approval/deployment is tested separately. Never enable
    this legacy switch in application deployment configuration.
    """
    modules={'test_flow_after_save','test_flow_pipeline','test_flow_resources','test_flow_self_update','test_flow_types'}
    name=request.node.originalname or request.node.name
    if request.module.__name__.rsplit('.',1)[-1] not in modules or not (
        name.startswith('test_real_http_') or name in {'test_field_list_date_screen_http_pipeline_and_compile_gate','test_capability_endpoint_matches_runtime_contract'}):
        yield
        return
    from Backend.AI.app.tests.test_workspace_regression import client as account_client
    from fastapi.testclient import TestClient as RealTestClient
    fixture=account_client.__wrapped__(tmp_path)
    next(fixture)
    class AuthenticatedLegacyClient(RealTestClient):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.cookies.set('app_session','session')
        def post(self,url,*args,**kwargs):
            if url=='/api/plan' and isinstance(kwargs.get('json'),dict):
                kwargs['json']={'target_org':'app_ours',**kwargs['json']}
            return super().post(url,*args,**kwargs)
    monkeypatch.setenv('APP_ENABLE_LEGACY_WORKFLOW','true')
    monkeypatch.setattr('Backend.AI.app.services.salesforce_metadata_api.owned_metadata_api',lambda *args:None)
    monkeypatch.setattr(request.module,'TestClient',AuthenticatedLegacyClient,raising=False)
    monkeypatch.setattr('fastapi.testclient.TestClient',AuthenticatedLegacyClient)
    try:
        yield
    finally:
        try:next(fixture)
        except StopIteration:pass
