"""Explicit configuration for the isolated Neon integration and cloud deployments."""

import os
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


def cloud_environment():
    return (
        bool(os.getenv("VERCEL"))
        or os.getenv("APP_ENV", "development") != "development"
    )


def local_path(value):
    value = value or "/"
    decoded = unquote(value)
    if (
        not decoded.startswith("/")
        or decoded.startswith("//")
        or "\\" in decoded
        or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
        or urlsplit(decoded).scheme
        or urlsplit(decoded).netloc
    ):
        return "/"
    return value


def normalized_email(value):
    return value.strip().lower() if isinstance(value, str) else ""


def allowed_emails():
    # Read on every authorization/delivery check, including existing sessions.
    return {
        normalized_email(value)
        for value in os.getenv("ALLOWED_EMAILS", "").split(",")
        if value.strip()
    }


def email_origins(settings):
    """Exact app origins served by the shared, signed delivery webhook."""
    origins = {settings.base_url}
    for value in os.getenv("AUTH_EMAIL_ORIGINS", "").split(","):
        value = value.strip().rstrip("/")
        if not value:
            continue
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and parsed.port in {None, 443}
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and "*" not in value
            )
        except ValueError:
            valid = False
        if not valid:
            raise RuntimeError("AUTH_EMAIL_ORIGINS requires exact HTTPS origins.")
        origins.add(value)
    return origins


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    base_url: str
    provider_url: str
    secure: bool

    @classmethod
    def from_env(cls):
        cloud = cloud_environment()
        mode = os.getenv("AUTH_MODE", "neon" if cloud else "password")
        base = os.getenv("APP_BASE_URL", "").rstrip("/")
        provider = os.getenv("NEON_AUTH_BASE_URL", "").rstrip("/")
        secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
        if mode not in {"password", "neon"} or (cloud and mode != "neon"):
            raise RuntimeError("Cloud deployments require AUTH_MODE=neon.")
        if cloud and (not os.getenv("SESSION_SECRET") or not secure):
            raise RuntimeError(
                "Cloud deployments require SESSION_SECRET and COOKIE_SECURE=true."
            )
        if mode == "neon":
            app = urlsplit(base)
            auth = urlsplit(provider)
            if not allowed_emails() or not os.getenv("SESSION_SECRET"):
                raise RuntimeError(
                    "Neon access requires ALLOWED_EMAILS and a stable SESSION_SECRET."
                )
            if (
                not app.hostname
                or app.username
                or app.password
                or app.query
                or app.fragment
                or app.path not in {"", "/"}
                or (
                    app.scheme != "https"
                    and not (
                        not cloud
                        and app.scheme == "http"
                        and app.hostname in {"localhost", "127.0.0.1"}
                    )
                )
            ):
                raise RuntimeError(
                    "APP_BASE_URL must be the exact HTTPS application origin (localhost allowed in development)."
                )
            if (
                auth.scheme != "https"
                or not auth.hostname
                or not auth.hostname.endswith(".neon.tech")
                or auth.username
                or auth.password
                or auth.query
                or auth.fragment
                or auth.port not in {None, 443}
                or not auth.path.endswith("/auth")
            ):
                raise RuntimeError(
                    "NEON_AUTH_BASE_URL must be the HTTPS branch Auth Base URL from Neon."
                )
        return cls(mode, base, provider, secure)


def database_url(migration=False):
    from sqlalchemy.engine import make_url

    raw = (os.getenv("MIGRATION_DATABASE_URL") if migration else None) or os.getenv(
        "DATABASE_URL"
    )
    if not raw:
        if cloud_environment() or os.getenv("AUTH_MODE") == "neon":
            raise RuntimeError(
                "DATABASE_URL is required; there is no deployed localhost fallback."
            )
        raw = "postgresql+psycopg://guardias:guardias@localhost:5433/guardias"
    url = make_url(raw)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if cloud_environment():
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or not url.host.endswith(".neon.tech")
        ):
            raise RuntimeError("Cloud deployments require a Neon PostgreSQL URL.")
        if url.query.get("sslmode") not in {"require", "verify-full", "verify-ca"}:
            raise RuntimeError(
                "Neon PostgreSQL connections require TLS (sslmode=require or stricter)."
            )
        if os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true":
            raise RuntimeError("SQL logging must be disabled for private deployments.")
    return url
