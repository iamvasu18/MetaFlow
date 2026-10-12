"""Offline container packaging check; no credentials or network calls."""
from pathlib import Path
import subprocess
from Backend.AI.app.services.hosting import install_frontend
from fastapi import FastAPI
from fastapi.testclient import TestClient

root = Path('/app')
assert (root / 'Frontend/dist/index.html').is_file()
assert (root / 'sfdx-project.json').is_file()
assert not (root / '.env').exists()
assert (root / 'deployment/demo.py').is_file()
subprocess.run(['node', '--version'], check=True)
subprocess.run(['node', '-e', "require('/app/tools/lwc/node_modules/@lwc/compiler')"], check=True)
app = FastAPI()
@app.get('/')
def legacy_root(): return {'message': 'backend running'}
install_frontend(app, root / 'Frontend/dist')
client = TestClient(app)
assert client.get('/').headers['content-type'].startswith('text/html')
assert client.get('/workspace').status_code == 200
assert client.get('/api/not-a-route').status_code == 404
print('Container packaging and SPA routing passed; no AI or Salesforce calls.')
