"""Free demo: supervise web and worker in one Render web-service instance."""
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event


def supervise(commands,stop,popen=subprocess.Popen):
    children=[]
    try:
        for command in commands:children.append(popen(command))
        while not stop.wait(1):
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Demo web or worker stopped; restarting the whole service is required.')
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=5)


def main():
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    stop=Event()
    for name in ('SIGINT','SIGTERM'):
        if hasattr(signal,name):signal.signal(getattr(signal,name),lambda *_:stop.set())
    supervise([[sys.executable,'deployment/start.py','web'],[sys.executable,'deployment/start.py','worker']],stop)


if __name__=='__main__':main()
