import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('demo_hosting',Path(__file__).resolve().parents[4]/'deployment/demo.py')
demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)


def test_worker_failure_stops_web():
    class Stop:
        def wait(self,n):return False
    class Process:
        def __init__(self,failed):self.failed=failed;self.terminated=False;self.waited=False
        def poll(self):return 1 if self.failed else None
        def terminate(self):self.terminated=True
        def wait(self,timeout):self.waited=True
    web,worker=Process(False),Process(True)
    children=iter([web,worker])
    with pytest.raises(RuntimeError):demo.supervise([['web'],['worker']],Stop(),popen=lambda cmd:next(children))
    assert web.terminated and web.waited and worker.waited


def test_shutdown_terminates_both():
    class Stop:
        def wait(self,n):return True
    class Process:
        terminated=False
        def poll(self):return None
        def terminate(self):self.terminated=True
        def wait(self,timeout):pass
    processes=[Process(),Process()];children=iter(processes)
    demo.supervise([['web'],['worker']],Stop(),popen=lambda cmd:next(children))
    assert all(p.terminated for p in processes)


def test_partial_start_failure_cleans_web():
    class Process:
        terminated=False
        def poll(self):return None
        def terminate(self):self.terminated=True
        def wait(self,timeout):pass
    web=Process()
    def popen(cmd):
        if cmd==['worker']:raise OSError('start failure')
        return web
    with pytest.raises(OSError):demo.supervise([['web'],['worker']],None,popen=popen)
    assert web.terminated
