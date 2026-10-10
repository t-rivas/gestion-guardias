"""Shared isolated Neon contract simulator, never connected to cloud services."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.auth_config import AuthSettings
from app.services.auth_webhooks import WebhookVerifier
from app.services.neon_auth import NeonAuth, SESSION_COOKIE

EMAIL = "thiago.rivas0021@gmail.com"
PROVIDER = "https://ep-test.neonauth.us-east-1.aws.neon.tech/neondb/auth"


def configure_neon(client, monkeypatch, base_url="https://testserver"):
    from app.main import app

    monkeypatch.setenv("ALLOWED_EMAILS", EMAIL)
    monkeypatch.setenv("SESSION_SECRET", "isolated-test-secret")
    client.base_url = httpx.URL(base_url)
    settings = AuthSettings("neon", base_url, PROVIDER, True)
    now = datetime.now(timezone.utc)
    state = {
        "calls": [],
        "used": False,
        "revoked": False,
        "outage": False,
        "identity": {
            "user": {"id": "owner", "email": EMAIL, "emailVerified": True},
            "session": {
                "userId": "owner",
                "createdAt": now.isoformat(),
                "expiresAt": (now + timedelta(days=7)).isoformat(),
            },
        },
    }
    key = Ed25519PrivateKey.generate()
    jwk = json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-key"
    state["key"] = key

    def upstream(request):
        state["calls"].append(request)
        if state["outage"]:
            return httpx.Response(503)
        operation = request.url.path.removeprefix("/neondb/auth/")
        if operation == ".well-known/jwks.json":
            return httpx.Response(200, json={"keys": [jwk]})
        if operation == "sign-in/magic-link":
            return httpx.Response(200, json={"status": True})
        if operation == "magic-link/verify":
            if request.url.params["token"] != "valid-token" or state["used"]:
                return httpx.Response(
                    302, headers={"location": "https://attacker.invalid"}
                )
            state["used"] = True
            return httpx.Response(
                302,
                headers=[
                    ("location", "https://attacker.invalid"),
                    (
                        "set-cookie",
                        f"{SESSION_COOKIE}=provider-token; Domain=neon.tech; Path=/neondb/auth; HttpOnly; Secure; SameSite=None; Partitioned",
                    ),
                    ("set-cookie", "unrelated=ignored; Path=/"),
                ],
            )
        if operation == "get-session":
            assert request.url.params["disableCookieCache"] == "true"
            if state[
                "revoked"
            ] or f"{SESSION_COOKIE}=provider-token" not in request.headers.get(
                "cookie", ""
            ):
                return httpx.Response(
                    200, content="null", headers={"content-type": "application/json"}
                )
            return httpx.Response(200, json=state["identity"])
        if operation == "sign-out":
            state["revoked"] = True
            return httpx.Response(200, json={"success": True})
        raise AssertionError(f"Unexpected operation: {operation}")

    auth = NeonAuth(settings, transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(app.state, "auth_settings", settings)
    monkeypatch.setattr(app.state, "neon_auth", auth)
    monkeypatch.setattr(app.state, "webhook_verifier", WebhookVerifier(auth))
    state["sent"] = []
    monkeypatch.setattr(
        app.state,
        "email_sender",
        lambda email, link: state["sent"].append((email, link)),
        raising=False,
    )
    state["client"] = client
    return state
