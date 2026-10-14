"""Launch Salesforce CLI without interpreting caller arguments in a shell."""
from pathlib import Path
import os
import shutil


def sf_arguments(arguments, *, windows=None):
    executable=shutil.which('sf')
    if not executable:raise RuntimeError("Salesforce CLI 'sf' was not found in PATH.")
    windows=os.name=='nt' if windows is None else windows
    if windows and Path(executable).suffix.lower() in {'.cmd','.bat'}:
        shim=Path(executable)
        candidates=[shim.parent/'run.js',shim.parent/'client/bin/run.js',
            shim.parent.parent/'client/bin/run.js',shim.parent.parent/'client/bin/run',
            shim.parent/'node_modules/@salesforce/cli/bin/run.js',
            shim.parent/'node_modules/@salesforce/cli/bin/run',
            shim.parent.parent/'node_modules/@salesforce/cli/bin/run.js']
        entry=next((p for p in candidates if p.is_file()),None)
        node=shim.parent/'node.exe'
        runtime=str(node) if node.is_file() else shutil.which('node')
        if entry is None or not runtime:
            raise RuntimeError('Cannot safely resolve the Windows Salesforce CLI Node entry point. Use a supported CLI installation; shell fallback is disabled.')
        return [runtime,str(entry),*arguments[1:]]
    return [executable,*arguments[1:]]
