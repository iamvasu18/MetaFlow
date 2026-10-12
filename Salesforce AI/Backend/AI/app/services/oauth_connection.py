"""Per-connection OAuth app credentials. Secrets are never returned to the UI."""
import json
import re
from urllib.parse import urlsplit
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


def auth_host(value):
    try:
        p=urlsplit(value)
        host=p.hostname or ''
        valid=host in {'login.salesforce.com','test.salesforce.com'} or bool(re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.my\.salesforce\.com',host))
        if p.scheme!='https' or not valid or p.port or p.username or p.password or p.path not in {'','/'} or p.query or p.fragment:
            raise ValueError()
    except (ValueError,TypeError):
        raise HTTPException(422,'Use an HTTPS Salesforce My Domain URL, without a path or port.') from None
    return 'https://' + host


class OAuthConnectionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',hide_input_in_errors=True)
    consumer_key: str=Field(min_length=10,max_length=512,repr=False)
    consumer_secret: str=Field(min_length=1,max_length=512,repr=False)
    org_url: str=Field(min_length=10,max_length=255)
    username: str=Field(min_length=3,max_length=255)


def connection_config(body,environment):
    host=auth_host(body.org_url.strip())
    if host in {'https://login.salesforce.com','https://test.salesforce.com'}:
        raise HTTPException(422,'Enter the specific org My Domain URL so the authorized org can be verified.')
    sandbox='.sandbox.my.salesforce.com' in host
    if (environment=='sandbox') != sandbox:
        raise HTTPException(422,'Choose the environment matching the org My Domain URL.')
    key=body.consumer_key.strip(); secret=body.consumer_secret.strip(); username=body.username.strip()
    if not key or not secret or not username or any(c.isspace() for c in key+secret+username):
        raise HTTPException(422,'Consumer credentials and Salesforce username must not contain whitespace.')
    return dict(client_id=key,client_secret=secret,auth_host=host,expected_instance=host,username=username,environment=environment)


def encrypt_config(config):
    from .integration_service import cipher
    return cipher().encrypt(json.dumps(config).encode()).decode()


def decrypt_config(payload):
    from .integration_service import cipher
    try:return json.loads(cipher().decrypt(payload.encode()))
    except Exception:raise HTTPException(503,'OAuth credentials cannot be decrypted. Restore the encryption key.') from None


def refresh_credentials(saved):
    config=saved.get('oauth_client')
    if config:
        if not isinstance(config,dict) or not config.get('client_id') or not config.get('client_secret'):
            raise HTTPException(503,'Saved OAuth application credentials are invalid. Reconnect this org.')
        return {'client_id':config['client_id'],'client_secret':config['client_secret']}
    # Backward compatibility for orgs connected with the shared application.
    import os
    from Backend.AI.app.account_api import client
    data={'client_id':client()}
    if os.getenv('SF_OAUTH_CLIENT_SECRET'):data['client_secret']=os.environ['SF_OAUTH_CLIENT_SECRET']
    return data
