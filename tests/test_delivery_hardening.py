"""Source-bound hardening controls; run only in the disposable verifier."""
import base64
import hashlib
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import HardenedFastAPI, app

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def client():
    peer = 'hardening-' + uuid4().hex
    async def scoped(scope, receive, send):
        if scope['type'] == 'http':
            scope = dict(scope, client=(peer, 40000))
        await app(scope, receive, send)
    with TestClient(scoped, raise_server_exceptions=False) as value:
        yield value


def assert_headers(response):
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['x-content-type-options'] == 'nosniff'
    csp = response.headers['content-security-policy']
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert 'access-control-allow-origin' not in response.headers
    assert 'set-cookie' not in response.headers

@pytest.mark.parametrize('path,status', [('/health',200),('/app',307),('/app/',200),('/app/app.js',200),('/does-not-exist',404)])
def test_headers_cover_app_static_redirect_and_404(client, path, status):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == status
    assert_headers(response)
    print('F_HEADER_PROOF',path,response.status_code)

@pytest.mark.parametrize('path',['/docs','/redoc','/openapi.json','/docs/oauth2-redirect'])
def test_public_api_discovery_disabled(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert_headers(response)
    print('F_DOCS_PROOF',path,response.status_code)


def test_debug_off_and_500_headers():
    assert app.debug is False
    isolated = HardenedFastAPI(debug=False, docs_url=None, redoc_url=None, openapi_url=None)
    @isolated.get('/deliberate-error')
    def deliberate_error():
        raise RuntimeError('synthetic-server-error-do-not-expose')
    with TestClient(isolated, raise_server_exceptions=False) as client:
        response = client.get('/deliberate-error')
        assert response.status_code == 500
        assert response.text == 'Internal Server Error'
        assert_headers(response)
    print('F_DEBUG_500_PROOF',False,500)


def test_cors_closed_and_auth_validation_headers(client):
    response = client.options('/auth/login',headers={'Origin':'https://not-allowed.invalid','Access-Control-Request-Method':'POST'})
    assert 'access-control-allow-origin' not in response.headers
    assert_headers(response)
    invalid = client.post('/auth/login',json={})
    assert invalid.status_code == 422
    assert_headers(invalid)
    print('F_CORS_PROOF',response.status_code,'no-cross-origin-grant',invalid.status_code)


def test_real_login_limiter_and_error_headers(client):
    username = 'f-proof-' + uuid4().hex
    statuses = []
    for _ in range(12):
        response = client.post('/auth/login',json={'username':username,'password':uuid4().hex})
        assert_headers(response)
        statuses.append(response.status_code)
        if response.status_code == 429:
            assert int(response.headers['retry-after']) > 0
            break
    assert statuses[0] == 401 and statuses[-1] == 429
    print('F_LIMITER_PROOF',statuses)


def test_existing_inline_script_is_authorized_by_exact_csp_hash(client):
    html = (ROOT/'web/index.html').read_text(encoding='utf-8')
    inline = re.findall(r'<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>', html, flags=re.DOTALL|re.IGNORECASE)
    assert inline, 'No inline-script positive control'
    csp = client.get('/app/').headers['content-security-policy']
    for script in inline:
        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        assert f"'sha256-{digest}'" in csp
    print('F_CSP_INLINE_PROOF',len(inline),'exact-hashes-authorized')

@pytest.mark.parametrize('module_name',['scripts.seed_demo_fresh','scripts.make_demo'])
@pytest.mark.parametrize('value',[None,'','x'*15,' '*20])
def test_seed_rejects_missing_or_short_environment_before_database(monkeypatch,module_name,value,capsys):
    module = importlib.import_module(module_name)
    if value is None:
        monkeypatch.delenv('SEED_USER_PASSWORD',raising=False)
    else:
        monkeypatch.setenv('SEED_USER_PASSWORD',value)
    class UnreachableDatabase:
        def begin(self):
            pytest.fail('Database reached before credential rejection')
    with pytest.raises(SystemExit,match='SEED_USER_PASSWORD'):
        module.seed(UnreachableDatabase())
    output = capsys.readouterr()
    assert not output.out and not output.err
    print('F_SEED_REFUSAL_PROOF',module_name,'missing' if value is None else len(value))

@pytest.mark.parametrize('module_name',['scripts.seed_demo_fresh','scripts.make_demo'])
def test_seed_accepts_environment_credential_verbatim(monkeypatch,module_name,capsys):
    module = importlib.import_module(module_name)
    value = ' ' + uuid4().hex[:16] + ' '
    monkeypatch.setenv('SEED_USER_PASSWORD',value)
    assert module._seed_password() == value
    output = capsys.readouterr()
    assert value not in output.out + output.err
    print('F_SEED_ENV_PROOF',module_name,'>=16','not-printed')


def test_database_default_is_fail_closed():
    env = dict(os.environ)
    env.pop('DATABASE_URL',None)
    result = subprocess.run([sys.executable,'-c','import app.db'],env=env,capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode != 0
    assert 'DATABASE_URL is required' in result.stderr
    print('F_NO_DB_DEFAULT_PROOF','refused-before-connect')


def test_compose_posting_default_and_required_credentials():
    source = (ROOT/'docker-compose.yml').read_text(encoding='utf-8')
    assert re.search(r'^\s+POSTING_ENABLED:\s*[\"\']?false[\"\']?\s*$',source,re.MULTILINE)
    for key in ('POSTGRES_USER','POSTGRES_PASSWORD','POSTGRES_DB','DATABASE_URL'):
        assert '${'+key+':?' in source
    from app.config import POSTING_ENABLED
    assert POSTING_ENABLED is False
    print('F_COMPOSE_DEFAULT_PROOF','posting=False','required-db-env=4')
