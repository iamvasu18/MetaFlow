import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from Backend.AI.app.services.hosting import install_frontend, validate_hosted_environment


def test_spa_preserves_api_and_blocks_paths(tmp_path):
    (tmp_path/'index.html').write_text('<html>MetaFlow</html>')
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets'/'app.js').write_text('console.log(1)')
    app=FastAPI()
    @app.get('/')
    def legacy_root(): return {'message':'backend running'}
    @app.get('/health')
    def health(): return {'status':'healthy'}
    @app.get('/api/example')
    def example(): return {'ok':True}
    install_frontend(app,tmp_path)
    client=TestClient(app)
    assert client.get('/').headers['content-type'].startswith('text/html')
    assert 'MetaFlow' in client.get('/').text
    assert client.get('/health').json()=={'status':'healthy'}
    assert client.get('/workspace').status_code == 200
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/api/example').json() == {'ok':True}
    for path in ['/api/missing','/assets/missing.js','/missing.js','/%2e%2e/secret']:
        assert client.get(path).status_code == 404


def test_requires_build(tmp_path):
    with pytest.raises(RuntimeError): install_frontend(FastAPI(),tmp_path)


def test_hosted_config(monkeypatch):
    values=dict(APP_DATABASE_URL='postgresql://localhost/db',APP_REDIS_URL='redis://localhost',
        APP_ENCRYPTION_KEY=Fernet.generate_key().decode(),APP_PUBLIC_URL='https://example.com',
        SF_OAUTH_CALLBACK_URL='https://example.com/api/orgs/callback',SF_OAUTH_CLIENT_ID='test',
        SF_OAUTH_CLIENT_SECRET='test',ANTHROPIC_API_KEY='test',ANTHROPIC_MODEL='test',
        APP_COOKIE_SECURE='true',APP_JOB_MODE='external',APP_BACKGROUND_JOBS='true',AI_PROVIDER='anthropic')
    for k,v in values.items(): monkeypatch.setenv(k,v)
    for name in ('SF_OAUTH_CLIENT_ID','SF_OAUTH_CLIENT_SECRET','ANTHROPIC_API_KEY','ANTHROPIC_MODEL'):
        monkeypatch.delenv(name, raising=False)
    validate_hosted_environment()
    monkeypatch.setenv('APP_PUBLIC_URL','http://example.com')
    with pytest.raises(RuntimeError): validate_hosted_environment()
    monkeypatch.setenv('APP_PUBLIC_URL',values['APP_PUBLIC_URL'])
    monkeypatch.setenv('SF_OAUTH_CALLBACK_URL','https://other.com/api/orgs/callback')
    with pytest.raises(RuntimeError): validate_hosted_environment()
