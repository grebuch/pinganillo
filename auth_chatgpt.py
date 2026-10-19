"""Official SIWC public-client OAuth. Tokens remain in memory only."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'


def validate_callback(params, state, client_id=None):
    if not secrets.compare_digest(params.get('state', [''])[0], state):
        raise ValueError('No se pudo verificar el inicio de sesión.')
    if params.get('error'):
        raise ValueError('Inicio de sesión cancelado o permiso no concedido.')
    issued = params.get('client_id', [client_id])[0]
    if not issued or issued == 'dynamic_agent_client' or (client_id and issued != client_id):
        raise ValueError('Registro de aplicación no válido.')
    code = params.get('code', [''])[0]
    if not code:
        raise ValueError('No se recibió autorización.')
    return issued, code


class ChatGPTAuth:
    def __init__(self):
        directory = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Escucha'
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'registro.json'
        if self.path.exists():
            self.config = json.loads(self.path.read_text(encoding='utf-8'))
        else:
            self.config = {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'registrations': []}
            self.save_config()
        self.tokens, self.identity, self.client_id = None, None, None
        self.discovery = None
        self.lock = threading.Lock()

    def save_config(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.config), encoding='utf-8')
        os.replace(temporary, self.path)

    def discover(self):
        import requests
        if self.discovery is None:
            r = requests.get(ISSUER + '/.well-known/openid-configuration', timeout=20)
            r.raise_for_status()
            config = r.json()
            if config['issuer'] != ISSUER:
                raise ValueError('Proveedor de identidad no válido.')
            for field in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
                if urlsplit(config[field]).scheme != 'https' or urlsplit(config[field]).netloc != 'auth.openai.com':
                    raise ValueError('Endpoint de identidad no válido.')
            self.discovery = config
        return self.discovery

    def verify(self, tokens, client_id, nonce=None, subject=None):
        import jwt
        discovery = self.discover()
        token = tokens['id_token']
        key = jwt.PyJWKClient(discovery['jwks_uri']).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=['RS256'], audience=client_id,
                            issuer=ISSUER, options={'require': ['exp', 'iss', 'aud', 'sub']})
        if nonce and not secrets.compare_digest(str(claims.get('nonce', '')), nonce):
            raise ValueError('No se pudo verificar la identidad.')
        if subject and claims['sub'] != subject:
            raise ValueError('La cuenta no coincide con el registro seleccionado.')
        scopes = tokens.get('scope', '').split()
        if 'chatgpt.tokens.use.direct' not in scopes:
            raise ValueError('No se autorizó el uso de tu plan ChatGPT. Vuelve a conectar y acepta ese permiso.')
        return claims

    def login(self, registration=None):
        import requests
        discovery = self.discover()
        state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        result = {}
        expected_id = registration['client_id'] if registration else None

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never log authorization codes.

            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path != '/auth/callback':
                    self.send_error(404)
                    return
                params = parse_qs(parsed.query)
                if params.get('state', [''])[0] != state:
                    self.send_error(400, 'Invalid state')
                    return
                try:
                    result['value'] = validate_callback(params, state, expected_id)
                    body = b'Autorizacion recibida. Puedes volver a Escucha.'
                except ValueError as exc:
                    result['error'] = exc
                    body = b'No se completo la autorizacion. Vuelve a Escucha.'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with HTTPServer(('127.0.0.1', 0), Callback) as server:
            server.timeout = .5
            redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
            params = {'client_id': expected_id or 'dynamic_agent_client',
                      'ext_agent_host_id': self.config['host_id'], 'response_type': 'code',
                      'redirect_uri': redirect, 'scope': 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct',
                      'resource': RESOURCE, 'state': state, 'nonce': nonce,
                      'code_challenge_method': 'S256', 'code_challenge': challenge}
            if expected_id:
                params['login_hint'] = registration.get('email', '')
            else:
                params['agent_name_hint'] = 'Escucha'
            webbrowser.open(discovery['authorization_endpoint'] + '?' + urlencode(params))
            deadline = time.monotonic() + 180
            while not result and time.monotonic() < deadline:
                server.handle_request()
            if not result:
                raise ValueError('Tiempo de conexión agotado. Pulsa Continue with ChatGPT de nuevo.')
        if result.get('error'):
            raise result['error']
        issued, code = result['value']
        response = requests.post(discovery['token_endpoint'], data={
            'grant_type': 'authorization_code', 'client_id': issued, 'code': code,
            'code_verifier': verifier, 'redirect_uri': redirect, 'resource': RESOURCE}, timeout=20)
        if not response.ok:
            raise ValueError(f'No se pudo completar la conexión (HTTP {response.status_code}). Vuelve a conectar.')
        tokens = response.json()
        identity = self.verify(tokens, issued, nonce, registration.get('subject') if registration else None)
        self.client_id, self.identity, self.tokens = issued, identity, tokens
        self.tokens['expires_at'] = time.time() + int(tokens.get('expires_in', 3600))
        record = {'client_id': issued, 'subject': identity['sub'], 'email': identity.get('email', '')}
        records = self.config['registrations']
        if not any(r['client_id'] == issued for r in records):
            records.append(record)
            self.save_config()
        return identity.get('email', identity['sub'])

    def access_token(self):
        import requests
        with self.lock:
            if not self.tokens:
                raise ValueError('Conecta tu cuenta ChatGPT primero.')
            if time.time() >= self.tokens['expires_at'] - 90:
                if not self.tokens.get('refresh_token'):
                    raise ValueError('Tu sesión ha caducado. Vuelve a conectar.')
                response = requests.post(self.discover()['token_endpoint'], data={
                    'grant_type': 'refresh_token', 'client_id': self.client_id,
                    'refresh_token': self.tokens['refresh_token'], 'resource': RESOURCE}, timeout=20)
                if not response.ok:
                    raise ValueError('No se pudo renovar tu sesión. Vuelve a conectar.')
                updated = response.json()
                if 'scope' not in updated:
                    updated['scope'] = self.tokens['scope']
                if updated.get('id_token'):
                    self.verify(updated, self.client_id, subject=self.identity['sub'])
                if 'chatgpt.tokens.use.direct' not in updated['scope'].split():
                    raise ValueError('El permiso de uso del plan ya no está activo.')
                self.tokens.update(updated)
                self.tokens['expires_at'] = time.time() + int(updated.get('expires_in', 3600))
            return self.tokens['access_token']

    def models(self):
        import requests
        r = requests.get(RESOURCE + '/models', headers={'Authorization': 'Bearer ' + self.access_token()}, timeout=20)
        if not r.ok:
            raise ValueError(f'No se pudieron consultar los modelos (HTTP {r.status_code}).')
        return [m for m in r.json().get('models', []) if m.get('visibility') == 'list']

    def logout(self):
        import requests
        confirmed = True
        try:
            if self.tokens and self.tokens.get('refresh_token'):
                endpoint = self.discover().get('revocation_endpoint')
                if not endpoint or urlsplit(endpoint).netloc != 'auth.openai.com' or urlsplit(endpoint).scheme != 'https':
                    confirmed = False
                else:
                    r = requests.post(endpoint, data={'token': self.tokens['refresh_token'],
                        'token_type_hint': 'refresh_token', 'client_id': self.client_id}, timeout=20)
                    confirmed = r.status_code == 200
        except Exception:
            confirmed = False
        finally:
            self.tokens, self.identity, self.client_id = None, None, None
        return confirmed
