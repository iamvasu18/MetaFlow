from pathlib import Path
import subprocess
from unittest.mock import Mock
import pytest
from Backend.AI.app.services.sf_process import sf_arguments


def test_native_arguments_do_not_interpret_shell_metacharacters(monkeypatch):
    monkeypatch.setattr('shutil.which',lambda name:'/usr/bin/sf')
    query="SELECT Id FROM Account WHERE Name = 'a&b | %PATH%'"
    assert sf_arguments(['sf','data','query','--query',query],windows=False)==['/usr/bin/sf','data','query','--query',query]


def test_windows_cmd_uses_node_entry_with_space_paths(tmp_path,monkeypatch):
    root=tmp_path/'Program Files'/'sf';(root/'bin').mkdir(parents=True);(root/'client/bin').mkdir(parents=True)
    shim=root/'bin/sf.cmd';shim.write_text('shim')
    entry=root/'client/bin/run.js';entry.write_text('entry')
    monkeypatch.setattr('shutil.which',lambda name:str(shim) if name=='sf' else 'node.exe')
    args=sf_arguments(['sf','data','query','--query','text & | %COMSPEC%'],windows=True)
    assert args==['node.exe',str(entry),'data','query','--query','text & | %COMSPEC%']


def test_unresolved_windows_shim_never_falls_back_to_shell(tmp_path,monkeypatch):
    monkeypatch.setattr('shutil.which',lambda name:str(tmp_path/'sf.cmd') if name=='sf' else 'node.exe')
    with pytest.raises(RuntimeError,match='shell fallback is disabled'):
        sf_arguments(['sf','--version'],windows=True)


def test_deployment_timeout_returns_unknown_without_resubmission(tmp_path,monkeypatch):
    from Backend.AI.app.services.deployment_executor import SalesforceDeploymentExecutor
    executor=SalesforceDeploymentExecutor(project_root=tmp_path)
    executor.build_command=Mock(return_value=['sf','project','deploy','start'])
    monkeypatch.setattr('Backend.AI.app.services.sf_process.sf_arguments',lambda args:args)
    run=Mock(side_effect=subprocess.TimeoutExpired('sf',180))
    monkeypatch.setattr(subprocess,'run',run)
    result=executor.deploy(Mock(id='PLAN-ONE',status='APPROVED'),{})
    assert result['operationStatus']=='unknown'
    assert result['reconciliationRequired'] is True
    assert run.call_count==1
    assert run.call_args.kwargs['timeout']==180
