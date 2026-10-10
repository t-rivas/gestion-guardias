"""Neon's documented detached JWS envelope; signatures use maintained libraries."""

import asyncio
import base64
import hashlib
import json
import os
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

import jwt
from sqlalchemy import delete, update

from app.auth_config import allowed_emails, local_path, normalized_email
from app.models.auth_delivery import AuthDelivery
from app.services.auth_storage import insert_for, take_rate_limit
from app.services.neon_auth import ProviderUnavailable


class InvalidWebhook(Exception):
    pass


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


class WebhookVerifier:
    def __init__(self, provider):
        self.provider = provider
        self.keys = {}
        self.fetched = 0
        self.lock = asyncio.Lock()

    async def verify(self, raw, headers, now=None):
        now = time.time() if now is None else now
        try:
            timestamp = headers["x-neon-timestamp"]
            if abs(now * 1000 - int(timestamp)) > 300_000:
                raise InvalidWebhook()
            signature = headers["x-neon-signature"]
            kid = headers["x-neon-signature-kid"]
            head, empty, tail = signature.split(".")
            protected = jwt.get_unverified_header(signature)
            if empty or protected.get("alg") != "EdDSA" or protected.get("kid") != kid:
                raise InvalidWebhook()
            async with self.lock:
                if now - self.fetched > 300 or (
                    kid not in self.keys and now - self.fetched >= 30
                ):
                    response = await self.provider.call(".well-known/jwks.json")
                    if response.status_code != 200:
                        raise ProviderUnavailable()
                    self.keys = {
                        key["kid"]: key
                        for key in response.json()["keys"]
                        if key.get("kty") == "OKP" and key.get("crv") == "Ed25519"
                    }
                    self.fetched = now
            if kid not in self.keys:
                raise InvalidWebhook()
            key = jwt.PyJWK.from_dict(self.keys[kid], algorithm="EdDSA").key
            payload = b64(f"{timestamp}.{b64(raw)}".encode())
            jwt.api_jws.decode_complete(
                f"{head}.{payload}.{tail}", key=key, algorithms=["EdDSA"]
            )
            data = json.loads(raw)
            if (
                data["event_id"] != headers["x-neon-event-id"]
                or data["event_type"] != headers["x-neon-event-type"]
                or str(UUID(data["event_id"])) != data["event_id"]
            ):
                raise InvalidWebhook()
            return data
        except (KeyError, ValueError, TypeError, jwt.PyJWTError):
            raise InvalidWebhook() from None


def delivery_link(data, settings):
    """Translate only a verified, branch-owned sign-in link to our fixed callback."""
    try:
        event = data["event_data"]
        link, provider = urlsplit(event["link_url"]), urlsplit(settings.provider_url)
        params = parse_qs(link.query, strict_parsing=True)
        token = event["token"]
        expiry = datetime.fromisoformat(event["expires_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if (
            event["link_type"] != "sign-in"
            or link.scheme != "https"
            or link.netloc != provider.netloc
            or link.path != provider.path + "/magic-link/verify"
            or link.username
            or link.password
            or link.fragment
            or not isinstance(token, str)
            or not token
            or len(token) > 1024
            or params.get("token") != [token]
            or not now < expiry
            or (expiry - now).total_seconds() > 16 * 60
        ):
            raise InvalidWebhook()
        for key in ("callbackURL", "newUserCallbackURL", "errorCallbackURL"):
            for target in params.get(key, []):
                parsed = urlsplit(target)
                if (
                    parsed.scheme or parsed.netloc
                ) and f"{parsed.scheme}://{parsed.netloc}" != settings.base_url:
                    raise InvalidWebhook()
                if local_path(parsed.path) != parsed.path:
                    raise InvalidWebhook()
        callback = params.get("callbackURL", ["/"])[0]
        parsed = urlsplit(callback)
        destination = local_path(
            parsed.path + ("?" + parsed.query if parsed.query else "")
        )
        return (
            settings.base_url
            + "/auth/callback?"
            + urlencode({"token": token, "next": destination})
        )
    except (KeyError, ValueError, TypeError, AttributeError):
        raise InvalidWebhook() from None


def send_email(recipient, link):
    # Only invoked after signature, allowlist, expiry, URL and shared-storage checks.
    host = os.getenv("SMTP_HOST")
    username, password = os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM")
    security = os.getenv("SMTP_SECURITY", "starttls")
    if not all((host, username, password, sender)) or security not in {
        "starttls",
        "ssl",
    }:
        raise RuntimeError(
            "Configure authenticated SMTP with TLS before requesting links."
        )
    message = EmailMessage()
    message["Subject"] = "Tu enlace para Gestión de guardias"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Ingresá a Gestión de guardias:\n\n{link}\n\nEl enlace se puede usar una sola vez y vence en 15 minutos.\nSi no lo solicitaste, ignorá este correo.\n"
    )
    port = int(os.getenv("SMTP_PORT", "587"))
    context = ssl.create_default_context()
    if security == "ssl":
        connection = smtplib.SMTP_SSL(host, port, timeout=3, context=context)
    else:
        connection = smtplib.SMTP(host, port, timeout=3)
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        smtp.login(username, password)
        smtp.send_message(message)


def deliver_event(data, raw, settings, factory, sender=send_email):
    recipient = normalized_email(data.get("user", {}).get("email"))
    if data["event_type"] == "user.before_create":
        return 200, {
            "allowed": recipient in allowed_emails(),
            "error_code": "PRIVATE_ACCESS",
        }
    if data["event_type"] != "send.magic_link":
        return 400, {"error": "unsupported_event"}
    if recipient not in allowed_emails():
        return 403, {"error": "delivery_denied"}
    link = delivery_link(data, settings)
    fingerprint = hashlib.sha256(raw).hexdigest()
    now = int(time.time())
    with factory() as db:
        # Retain receipts longer than the signature replay window; no link/recipient stored.
        db.execute(delete(AuthDelivery).where(AuthDelivery.created_at < now - 86400))
        statement = (
            insert_for(db, AuthDelivery)
            .values(
                event_id=data["event_id"],
                fingerprint=fingerprint,
                state="claimed",
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=[AuthDelivery.event_id])
            .returning(AuthDelivery.event_id)
        )
        claimed = db.execute(statement).scalar_one_or_none()
        db.commit()
        if not claimed:
            receipt = db.get(AuthDelivery, data["event_id"])
            if receipt.fingerprint != fingerprint:
                return 409, {"error": "event_conflict"}
            return (
                (200, {"ok": True})
                if receipt.state == "sent"
                else (503, {"error": "request_new_link"})
            )
        if not take_rate_limit(db, "delivery", recipient, os.environ["SESSION_SECRET"]):
            db.execute(
                update(AuthDelivery)
                .where(AuthDelivery.event_id == claimed)
                .values(state="failed")
            )
            db.commit()
            return 429, {"error": "request_new_link"}
        try:
            sender(recipient, link)
        except Exception:
            # SMTP may have accepted mail before timing out. Never resend this event.
            state = "failed"
        else:
            state = "sent"
        db.execute(
            update(AuthDelivery)
            .where(AuthDelivery.event_id == claimed)
            .values(state=state)
        )
        db.commit()
    return (
        (200, {"ok": True}) if state == "sent" else (503, {"error": "request_new_link"})
    )
