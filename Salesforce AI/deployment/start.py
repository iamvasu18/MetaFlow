"""Container entry point: python deployment/start.py web|worker."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
if os.getenv('APP_PUBLIC_URL') and not os.getenv('SF_OAUTH_CALLBACK_URL'):
    os.environ['SF_OAUTH_CALLBACK_URL'] = os.environ['APP_PUBLIC_URL'].rstrip('/') + '/api/orgs/callback'
from Backend.AI.app.services.hosting import validate_hosted_environment
validate_hosted_environment()

if len(sys.argv) != 2 or sys.argv[1] not in {'web', 'worker'}:
    raise SystemExit('Use web or worker.')

# Initializes the schema under the existing cross-process Postgres advisory lock.
from Backend.AI.app.account_api import db
with db() as connection:
    connection.execute('SELECT 1')

if sys.argv[1] == 'worker':
    from Backend.AI.app.job_worker import main
    main()
else:
    from Backend.AI.app.main import app
    from Backend.AI.app.services.hosting import install_frontend
    from fastapi.responses import JSONResponse

    @app.get('/ready', include_in_schema=False)
    def ready():
        try:
            with db() as connection:
                connection.execute('SELECT 1')
            return {'status': 'ready'}
        except Exception:
            return JSONResponse({'status': 'unavailable'}, status_code=503)

    install_frontend(app, ROOT / 'Frontend' / 'dist')
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '10000')),
                access_log=False, proxy_headers=True,
                forwarded_allow_ips=os.getenv('FORWARDED_ALLOW_IPS', '127.0.0.1'))
