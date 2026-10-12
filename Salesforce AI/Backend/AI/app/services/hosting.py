"""Hosting checks and SPA routing; no changes to metadata approvals."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles


def validate_hosted_environment():
    required = ('APP_DATABASE_URL', 'APP_REDIS_URL', 'APP_ENCRYPTION_KEY',
                'APP_PUBLIC_URL',
                'SF_OAUTH_CALLBACK_URL')
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if missing:
        raise RuntimeError('Missing hosted configuration: ' + ', '.join(missing))
    Fernet(os.environ['APP_ENCRYPTION_KEY'].encode())
    url = os.environ['APP_PUBLIC_URL'].rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise RuntimeError('APP_PUBLIC_URL must be an HTTPS origin.')
    if os.environ['SF_OAUTH_CALLBACK_URL'] != url + '/api/orgs/callback':
        raise RuntimeError('OAuth callback must match the public origin and /api/orgs/callback.')
    if os.getenv('APP_COOKIE_SECURE') != 'true' or os.getenv('APP_JOB_MODE') != 'external' or os.getenv('APP_BACKGROUND_JOBS') != 'true':
        raise RuntimeError('Hosting requires secure cookies and external background jobs.')
    if os.getenv('AI_PROVIDER') not in {'anthropic','openai','gemini'}:
        raise RuntimeError('Choose a supported AI provider.')
    if not os.environ['APP_DATABASE_URL'].startswith(('postgresql://', 'postgres://')):
        raise RuntimeError('Hosting requires Postgres.')


def install_frontend(app, directory):
    root = Path(directory).resolve()
    if not (root / 'index.html').is_file() or not (root / 'assets').is_dir():
        raise RuntimeError('Frontend build is missing.')
    app.mount('/assets', StaticFiles(directory=root / 'assets'), name='frontend_assets')

    @app.get('/{frontend_path:path}', include_in_schema=False)
    def frontend(frontend_path: str):
        if frontend_path.split('/')[0] in {'api', 'health', 'ready', 'assets'}:
            raise HTTPException(404, 'Not found')
        candidate = (root / frontend_path).resolve()
        if not candidate.is_relative_to(root):
            raise HTTPException(404, 'Not found')
        if candidate.is_file():
            return FileResponse(candidate)
        # Missing asset requests must not receive index.html.
        if Path(frontend_path).suffix:
            raise HTTPException(404, 'Not found')
        return FileResponse(root / 'index.html', headers={'Cache-Control': 'no-cache'})
