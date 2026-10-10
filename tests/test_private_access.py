"""Isolated provider-contract tests. These do not prove live Neon/email behavior."""

import json
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
import pytest

from app.auth_config import AuthSettings, database_url, local_path
from app.models import Account, AuthDelivery, Person
from app.services.auth_storage import take_rate_limit
from app.services.auth_webhooks import b64
from app.services.neon_auth import SESSION_COOKIE
from tests.conftest import token

EMAIL = "thiago.rivas0021@gmail.com"
PROVIDER = "https://ep-test.neonauth.us-east-1.aws.neon.tech/neondb/auth"


def signed_in(neon):
    client = neon["client"]
    response = client.get(
        "/auth/callback?token=valid-token&next=/personas", follow_redirects=False
    )
    assert response.status_code == 303
    return client


@pytest.mark.parametrize(
    "path", ["/", "/personas", "/disponibilidad", "/calendario", "/a-future-route"]
)
def test_anonymous_pages(neon, path):
    response = neon["client"].get(path, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith(
        "/login?"
    )
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.parametrize(
    "path",
    [
        "/personas",
        "/personas/1/editar",
        "/personas/1/desactivar",
        "/disponibilidad/toggle",
        "/disponibilidad/guardar",
        "/calendario/generar",
        "/calendario/editar",
        "/calendario/intercambiar",
        "/calendario/versiones/1/aplicar",
    ],
)
def test_anonymous_writes_leave_data_unchanged(neon, db, path):
    assert neon["client"].post(path, data={"full_name": "Denied"}).status_code == 401
    assert db.query(Person).count() == 0


@pytest.mark.parametrize("kind", ["csv", "ics"])
def test_anonymous_exports(neon, kind):
    assert (
        neon["client"].get(f"/calendario/exportar/{kind}?year=2026&month=3").status_code
        == 401
    )


def test_legacy_account_cannot_bypass_neon(neon, db):
    from app.security import password_hash

    db.add(
        Account(
            id=1, username="admin", password_hash=password_hash("existing-password")
        )
    )
    db.commit()
    c = neon["client"]
    assert c.get("/setup").status_code == 404
    assert c.post("/setup", data={}).status_code == 404
    csrf = token(c.get("/login"))
    response = c.post(
        "/login",
        data={"csrf_token": csrf, "username": "admin", "password": "existing-password"},
    )
    assert "Si el correo tiene acceso" in response.text
    assert c.get("/personas", follow_redirects=False).status_code == 303
    assert db.get(Account, 1) is not None


def test_generic_login_cooldown_and_csrf(neon):
    c = neon["client"]
    page = c.get("/login")
    assert page.headers["referrer-policy"] == "same-origin"
    csrf = token(page)
    assert c.post("/login", data={"email": EMAIL}).status_code == 403
    assert (
        c.post(
            "/login",
            data={"email": EMAIL, "csrf_token": csrf},
            headers={"origin": "https://evil.invalid"},
        ).status_code
        == 403
    )
    approved = c.post(
        "/login",
        data={"email": EMAIL.upper(), "csrf_token": csrf, "next": "//evil.invalid"},
    )
    denied = c.post(
        "/login", data={"email": "stranger@example.com", "csrf_token": csrf}
    )
    assert approved.text == denied.text
    assert approved.headers["retry-after"] == "60"
    c.post("/login", data={"email": EMAIL, "csrf_token": csrf})
    assert len(neon["calls"]) == 1
    body = json.loads(neon["calls"][0].content)
    assert body["email"] == EMAIL and body["callbackURL"] == "https://testserver/"


def test_callback_session_cookie_scope_logout_and_reuse(neon):
    c = neon["client"]
    response = c.get(
        "/auth/callback?token=valid-token&next=//evil.invalid", follow_redirects=False
    )
    assert response.headers["location"] == "/"
    assert response.headers["referrer-policy"] == "no-referrer"
    cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(
        cookie for cookie in cookies if cookie.startswith(SESSION_COOKIE)
    )
    assert "Domain=" not in auth_cookie and "Partitioned" not in auth_cookie
    assert "Path=/" in auth_cookie and "SameSite=lax" in auth_cookie
    assert "Secure" in auth_cookie and "HttpOnly" in auth_cookie
    assert "unrelated" not in c.cookies
    assert c.get("/personas").status_code == 200
    assert (
        c.get("/auth/callback?token=valid-token", follow_redirects=False).headers[
            "location"
        ]
        == "/login?error=expired"
    )
    csrf = token(c.get("/personas"))
    assert (
        c.post("/logout", data={"csrf_token": csrf}, follow_redirects=False).status_code
        == 303
    )
    assert neon["revoked"]
    c.cookies.set(SESSION_COOKIE, "provider-token")
    assert c.get("/personas", follow_redirects=False).status_code == 303


def test_whitelist_removal_and_provider_failure(neon, monkeypatch, db):
    c = signed_in(neon)
    assert c.get("/personas").status_code == 200
    monkeypatch.setenv("ALLOWED_EMAILS", "somebody@example.com")
    assert c.get("/personas", follow_redirects=False).status_code == 303
    assert c.post("/personas", data={"full_name": "Denied"}).status_code == 401
    monkeypatch.setenv("ALLOWED_EMAILS", EMAIL)
    neon["outage"] = True
    assert c.get("/personas").status_code == 503
    assert c.post("/personas", data={"full_name": "Denied"}).status_code == 503
    assert db.query(Person).count() == 0


@pytest.mark.parametrize(
    "invalid", ["unverified", "expired", "old", "wrong-user", "tampered-cookie"]
)
def test_invalid_sessions(neon, invalid):
    c = signed_in(neon)
    now = datetime.now(timezone.utc)
    identity = neon["identity"]
    if invalid == "unverified":
        identity["user"]["emailVerified"] = False
    elif invalid == "expired":
        identity["session"]["expiresAt"] = (now - timedelta(seconds=1)).isoformat()
    elif invalid == "old":
        identity["session"]["createdAt"] = (now - timedelta(days=8)).isoformat()
        identity["session"]["expiresAt"] = (now + timedelta(days=1)).isoformat()
    elif invalid == "wrong-user":
        identity["session"]["userId"] = "attacker"
    else:
        c.cookies.clear()
        c.cookies.set(SESSION_COOKIE, "forged")
    assert c.get("/personas", follow_redirects=False).status_code == 303


def event(email=EMAIL, event_type="send.magic_link"):
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "user": {"email": email},
        "event_data": {
            "link_type": "sign-in",
            "token": "valid-token",
            "link_url": PROVIDER
            + "/magic-link/verify?token=valid-token&callbackURL=https%3A%2F%2Ftestserver%2Fpersonas",
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=15)
            ).isoformat(),
        },
    }


def signed_webhook(neon, data, timestamp=None):
    raw = json.dumps(data).encode()
    timestamp = str(int(time.time() * 1000)) if timestamp is None else str(timestamp)
    complete = jwt.api_jws.encode(
        f"{timestamp}.{b64(raw)}".encode(),
        neon["key"],
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )
    head, _, tail = complete.split(".")
    return raw, {
        "x-neon-signature": f"{head}..{tail}",
        "x-neon-signature-kid": "test-key",
        "x-neon-timestamp": timestamp,
        "x-neon-event-id": data["event_id"],
        "x-neon-event-type": data["event_type"],
    }


def test_webhook_signature_delivery_and_idempotent_retry(neon, db):
    data = event()
    raw, headers = signed_webhook(neon, data)
    c = neon["client"]
    assert (
        c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code == 200
    )
    assert (
        c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code == 200
    )
    assert len(neon["sent"]) == 1
    assert neon["sent"][0][0] == EMAIL
    assert neon["sent"][0][1].startswith("https://testserver/auth/callback?")
    assert db.query(AuthDelivery).one().state == "sent"
    # The same ID with a differently signed body may not change its original delivery.
    data["event_data"]["token"] = "other"
    data["event_data"]["link_url"] = data["event_data"]["link_url"].replace(
        "valid-token", "other"
    )
    raw, headers = signed_webhook(neon, data)
    assert (
        c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code == 409
    )
    assert len(neon["sent"]) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        "tamper",
        "stale",
        "future",
        "header-id",
        "header-event",
        "kid",
        "unapproved",
        "url",
        "redirect",
        "expired",
        "type",
    ],
)
def test_invalid_or_unapproved_webhooks_never_send(neon, invalid):
    data = event()
    timestamp = None
    if invalid == "unapproved":
        data["user"]["email"] = "stranger@example.com"
    elif invalid == "url":
        data["event_data"]["link_url"] = "https://evil.invalid/?token=valid-token"
    elif invalid == "redirect":
        data["event_data"]["link_url"] += "&errorCallbackURL=https://evil.invalid"
    elif invalid == "expired":
        data["event_data"]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
    elif invalid == "type":
        data["event_data"]["link_type"] = "forget-password"
    elif invalid in {"stale", "future"}:
        timestamp = int(time.time() * 1000) + (
            -600000 if invalid == "stale" else 600000
        )
    raw, headers = signed_webhook(neon, data, timestamp)
    if invalid == "tamper":
        raw += b" "
    elif invalid == "header-id":
        headers["x-neon-event-id"] = str(uuid4())
    elif invalid == "header-event":
        headers["x-neon-event-type"] = "user.before_create"
    elif invalid == "kid":
        headers["x-neon-signature-kid"] = "wrong-key"
    assert neon["client"].post(
        "/webhooks/neon-auth", content=raw, headers=headers
    ).status_code in {400, 403}
    assert neon["sent"] == []


def test_direct_provider_signup_policy_and_delivery_rate_limit(neon):
    c = neon["client"]
    for email, allowed in [(EMAIL, True), ("stranger@example.com", False)]:
        raw, headers = signed_webhook(neon, event(email, "user.before_create"))
        assert (
            c.post("/webhooks/neon-auth", content=raw, headers=headers).json()[
                "allowed"
            ]
            is allowed
        )
    raw, headers = signed_webhook(neon, event())
    assert (
        c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code == 200
    )
    raw, headers = signed_webhook(neon, event())
    assert (
        c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code == 429
    )
    assert len(neon["sent"]) == 1


def test_sender_failure_never_resends_uncertain_event(neon, monkeypatch, db):
    from app.main import app

    attempts = []

    def failing(email, link):
        attempts.append(email)
        raise TimeoutError("simulated SMTP acknowledgement loss")

    monkeypatch.setattr(app.state, "email_sender", failing)
    raw, headers = signed_webhook(neon, event())
    c = neon["client"]
    for _ in range(3):
        assert (
            c.post("/webhooks/neon-auth", content=raw, headers=headers).status_code
            == 503
        )
    assert attempts == [EMAIL]
    assert db.query(AuthDelivery).one().state == "failed"


def test_shared_rate_limits_across_sessions(factory):
    with factory() as db:
        assert take_rate_limit(db, "test", EMAIL, "secret", now=100)
    with factory() as other_instance:
        assert not take_rate_limit(other_instance, "test", EMAIL, "secret", now=101)
        assert take_rate_limit(other_instance, "test", EMAIL, "secret", now=160)


@pytest.mark.parametrize(
    "path",
    [
        "//evil.invalid",
        "https://evil.invalid",
        "/\\evil.invalid",
        "/%5cevil.invalid",
        "/%2fevil.invalid",
        "/foo%0d%0aLocation:evil",
    ],
)
def test_hostile_return_paths(path):
    assert local_path(path) == "/"


@pytest.mark.parametrize(
    "name,value",
    [
        ("AUTH_MODE", "password"),
        ("SESSION_SECRET", ""),
        ("COOKIE_SECURE", "false"),
        ("ALLOWED_EMAILS", ""),
        ("NEON_AUTH_BASE_URL", "https://evil.invalid/auth"),
        ("APP_BASE_URL", "http://testserver"),
    ],
)
def test_cloud_config_fails_closed(monkeypatch, name, value):
    for key, val in {
        "VERCEL": "1",
        "AUTH_MODE": "neon",
        "SESSION_SECRET": "stable-secret",
        "COOKIE_SECURE": "true",
        "ALLOWED_EMAILS": EMAIL,
        "NEON_AUTH_BASE_URL": PROVIDER,
        "APP_BASE_URL": "https://testserver",
    }.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        AuthSettings.from_env()


def test_cloud_database_tls_and_no_fallback(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        database_url()
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:password@ep-test.neon.tech/neondb"
    )
    with pytest.raises(RuntimeError):
        database_url()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@ep-test.neon.tech/neondb?sslmode=require",
    )
    assert database_url().drivername == "postgresql+psycopg"
