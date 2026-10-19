"""Sign in with ChatGPT (open-source / local client contract).

Flow: OpenID Connect authorization code + PKCE through the system browser and a
one-shot HTTP listener on 127.0.0.1. The ID token is verified against OpenAI's
JWKS (signature, issuer, audience, expiry, nonce) and the
``chatgpt.tokens.use.direct`` scope must be granted before any plan usage.

Security choices:
* Tokens live in memory only. Closing the app forgets them.
* Only non-secret registration data is persisted (issued client id, subject,
  email and a random host id), so the same installation is recognised later.
* Authorization codes are never logged.

Docs: https://developers.openai.com/siwc/token-sharing-open-source/sign-in
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"
APP_NAME = "Pinganillo"
LOGIN_TIMEOUT_S = 180


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "Pinganillo"


def validate_callback(
    params: dict[str, list[str]], state: str, client_id: str | None = None
) -> tuple[str, str]:
    """Check the redirect parameters and return ``(issued_client_id, code)``."""
    if not secrets.compare_digest(params.get("state", [""])[0], state):
        raise ValueError("Sign-in could not be verified (state mismatch).")
    if params.get("error"):
        raise ValueError("Sign-in cancelled or permission not granted.")
    issued = params.get("client_id", [client_id])[0]
    if not issued or issued == "dynamic_agent_client" or (client_id and issued != client_id):
        raise ValueError("Invalid application registration.")
    code = params.get("code", [""])[0]
    if not code:
        raise ValueError("No authorization code received.")
    return issued, code


def _https_on_issuer(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc == urlsplit(ISSUER).netloc


class ChatGPTAuth:
    def __init__(self, directory: Path | None = None) -> None:
        directory = directory or config_dir()
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "chatgpt_registrations.json"
        self.config = self._load_config()
        self.tokens: dict[str, Any] | None = None
        self.identity: dict[str, Any] | None = None
        self.client_id: str | None = None
        self.discovery: dict[str, Any] | None = None
        self.lock = threading.Lock()

    # -- persistence -------------------------------------------------------
    def _load_config(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data.get("host_id"), str) and isinstance(data.get("registrations"), list):
                return data
        except (OSError, ValueError):
            pass  # Missing or corrupt: start a fresh registration file.
        data = {"host_id": "urn:uuid:" + str(uuid.uuid4()), "registrations": []}
        self.config = data
        self.save_config()
        return data

    def save_config(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.config), encoding="utf-8")
        os.replace(temporary, self.path)  # atomic on Windows and POSIX

    @property
    def registrations(self) -> list[dict[str, str]]:
        return self.config["registrations"]

    @property
    def connected(self) -> bool:
        return self.tokens is not None

    # -- OpenID ------------------------------------------------------------
    def discover(self) -> dict[str, Any]:
        import requests

        if self.discovery is None:
            r = requests.get(ISSUER + "/.well-known/openid-configuration", timeout=20)
            r.raise_for_status()
            config = r.json()
            if config["issuer"] != ISSUER:
                raise ValueError("Unexpected identity provider.")
            for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not _https_on_issuer(config[field]):
                    raise ValueError("Unexpected identity endpoint.")
            self.discovery = config
        return self.discovery

    def verify(
        self, tokens: dict[str, Any], client_id: str, nonce: str | None = None, subject: str | None = None
    ) -> dict[str, Any]:
        import jwt

        token = tokens["id_token"]
        key = jwt.PyJWKClient(self.discover()["jwks_uri"]).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if nonce and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise ValueError("Identity could not be verified (nonce mismatch).")
        if subject and claims["sub"] != subject:
            raise ValueError("The account does not match the selected registration.")
        if PLAN_SCOPE not in tokens.get("scope", "").split():
            raise ValueError("ChatGPT plan usage was not authorised. Reconnect and accept that permission.")
        return claims

    def login(self, registration: dict[str, str] | None = None) -> str:
        """Run the browser flow; returns the account email (or subject)."""
        import requests

        discovery = self.discover()
        state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        result: dict[str, Any] = {}
        expected_id = registration["client_id"] if registration else None

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass  # Never log authorization codes.

            def do_GET(self) -> None:
                parsed = urlsplit(self.path)
                if parsed.path != "/auth/callback":
                    self.send_error(404)
                    return
                params = parse_qs(parsed.query)
                if params.get("state", [""])[0] != state:
                    self.send_error(400, "Invalid state")
                    return
                try:
                    result["value"] = validate_callback(params, state, expected_id)
                    body = b"Authorisation received. You can go back to Pinganillo."
                except ValueError as exc:
                    result["error"] = exc
                    body = b"Authorisation was not completed. Go back to Pinganillo."
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with HTTPServer(("127.0.0.1", 0), Callback) as server:
            server.timeout = 0.5
            redirect = f"http://127.0.0.1:{server.server_port}/auth/callback"
            params = {
                "client_id": expected_id or "dynamic_agent_client",
                "ext_agent_host_id": self.config["host_id"],
                "response_type": "code",
                "redirect_uri": redirect,
                "scope": SCOPES,
                "resource": RESOURCE,
                "state": state,
                "nonce": nonce,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
            if registration:
                params["login_hint"] = registration.get("email", "")
            else:
                params["agent_name_hint"] = APP_NAME
            webbrowser.open(discovery["authorization_endpoint"] + "?" + urlencode(params))
            deadline = time.monotonic() + LOGIN_TIMEOUT_S
            while not result and time.monotonic() < deadline:
                server.handle_request()
            if not result:
                raise ValueError("Sign-in timed out. Press 'Continue with ChatGPT' again.")
        if result.get("error"):
            raise result["error"]
        issued, code = result["value"]
        response = requests.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": issued,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect,
                "resource": RESOURCE,
            },
            timeout=20,
        )
        if not response.ok:
            raise ValueError(f"Could not complete sign-in (HTTP {response.status_code}). Try again.")
        tokens = response.json()
        identity = self.verify(tokens, issued, nonce, registration.get("subject") if registration else None)
        self.client_id, self.identity, self.tokens = issued, identity, tokens
        self.tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
        if not any(r["client_id"] == issued for r in self.registrations):
            self.registrations.append(
                {"client_id": issued, "subject": identity["sub"], "email": identity.get("email", "")}
            )
            self.save_config()
        return identity.get("email", identity["sub"])

    def access_token(self) -> str:
        """Current access token, refreshed 90 s before expiry."""
        import requests

        with self.lock:
            if not self.tokens or not self.identity:
                raise ValueError("Connect your ChatGPT account first.")
            if time.time() >= self.tokens["expires_at"] - 90:
                if not self.tokens.get("refresh_token"):
                    raise ValueError("Your session expired. Reconnect.")
                response = requests.post(
                    self.discover()["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "refresh_token": self.tokens["refresh_token"],
                        "resource": RESOURCE,
                    },
                    timeout=20,
                )
                if not response.ok:
                    raise ValueError("Could not refresh your session. Reconnect.")
                updated = response.json()
                updated.setdefault("scope", self.tokens["scope"])
                if updated.get("id_token"):
                    self.verify(updated, str(self.client_id), subject=self.identity["sub"])
                if PLAN_SCOPE not in updated["scope"].split():
                    raise ValueError("ChatGPT plan usage permission is no longer active.")
                self.tokens.update(updated)
                self.tokens["expires_at"] = time.time() + int(updated.get("expires_in", 3600))
            return str(self.tokens["access_token"])

    def models(self) -> list[dict[str, Any]]:
        """Models available to the signed-in account (``models[].slug``, ``display_name``)."""
        import requests

        r = requests.get(
            RESOURCE + "/models", headers={"Authorization": "Bearer " + self.access_token()}, timeout=20
        )
        if not r.ok:
            raise ValueError(f"Could not list models (HTTP {r.status_code}).")
        return [m for m in r.json().get("models", []) if m.get("visibility") == "list"]

    def logout(self) -> bool:
        """Forget tokens locally and try to revoke remotely; returns True if revocation was confirmed."""
        import requests

        confirmed = True
        try:
            if self.tokens and self.tokens.get("refresh_token"):
                endpoint = self.discover().get("revocation_endpoint")
                if not endpoint or not _https_on_issuer(endpoint):
                    confirmed = False
                else:
                    r = requests.post(
                        endpoint,
                        data={
                            "token": self.tokens["refresh_token"],
                            # "refresh_token" below is the token *type* name (RFC 7009), not a secret.
                            "token_type_hint": "refresh_token",  # nosec B105
                            "client_id": self.client_id,
                        },
                        timeout=20,
                    )
                    confirmed = r.status_code == 200
        except Exception:
            confirmed = False
        finally:
            self.tokens, self.identity, self.client_id = None, None, None
        return confirmed
