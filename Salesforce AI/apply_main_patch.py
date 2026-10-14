"""Run from Salesforce AI. Preserve current main.py, including logging changes."""
from pathlib import Path

path = Path('Backend/AI/app/main.py')
source = path.read_text(encoding='utf-8-sig')
old = "    if package['state'] not in {'pending','unknown'}:\n        return default_package_response(plan_id)"
new = "    if package['state'] not in {'pending','unknown','failed'}:\n        return default_package_response(plan_id)"
if new in source:
    print('Failed-job report refresh is already installed.')
elif source.count(old) == 1:
    updated = source.replace(old, new)
    compile(updated, str(path), 'exec')
    path.write_text(updated, encoding='utf-8')
    print('Failed-job report refresh installed; other main.py code preserved.')
else:
    raise SystemExit('main.py differs from the reviewed source. No file changed; send report_default_package for review.')
