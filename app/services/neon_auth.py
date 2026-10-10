"""Small server-only bridge. No general proxy and no local auth token minting."""

from datetime import datetime, timezone
from http.cookies import SimpleCookie
import re

import httpx

from app.auth_config import allowed_emails, normalized_email

SESSION_COOKIE = "__Secure-neon-auth.session_token"
SESSION_SECONDS = 7 * 24 * 60 * 60


class ProviderUnavailable(Exception):
    pass


def session_cookies(cookies):
    # Cached identity cookies are deliberately never used for authorization.
    return (
        {SESSION_COOKIE: cookies[SESSION_COOKIE]} if cookies.get(SESSION_COOKIE) else {}
    )


def response_cookies(response):
    cookies = {}
    for header in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(re.sub(r";\s*Partitioned\b", "", header, flags=re.IGNORECASE))
        for name, morsel in parsed.items():
            if name == SESSION_COOKIE:
                cookies[name] = morsel.value
    return cookies


def apply_cookies(response, upstream, secure=True):
    # Iterate independent headers: never comma-join Set-Cookie.
    for header in upstream.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(re.sub(r";\s*Partitioned\b", "", header, flags=re.IGNORECASE))
        for name, morsel in parsed.items():
            if name != SESSION_COOKIE:
                continue
            max_age = SESSION_SECONDS
            if morsel["max-age"]:
                max_age = min(SESSION_SECONDS, max(0, int(morsel["max-age"])))
            response.set_cookie(
                name,
                morsel.value,
                max_age=max_age,
                path="/",
                secure=secure,
                httponly=True,
                samesite="lax",
            )


def verified_identity(payload, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        user, session = payload["user"], payload["session"]
        created = datetime.fromisoformat(session["createdAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(session["expiresAt"].replace("Z", "+00:00"))
        valid = (
            user.get("emailVerified") is True
            and user.get("banned") is not True
            and user.get("id")
            and user["id"] == session.get("userId")
            and normalized_email(user.get("email")) in allowed_emails()
            and created <= now < expires
            and (now - created).total_seconds() < SESSION_SECONDS
        )
        return user if valid else None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


class NeonAuth:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def call(
        self, operation, method="GET", *, cookies=None, params=None, body=None
    ):
        if (method, operation) not in {
            ("POST", "sign-in/magic-link"),
            ("GET", "magic-link/verify"),
            ("GET", "get-session"),
            ("POST", "sign-out"),
            ("GET", ".well-known/jwks.json"),
        }:
            raise ValueError("Unsupported auth operation")
        try:
            # A fresh client prevents sharing one user's upstream cookie jar with another.
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=8,
                follow_redirects=False,
                cookies=session_cookies(cookies or {}),
            ) as client:
                response = await client.request(
                    method,
                    f"{self.settings.provider_url}/{operation}",
                    headers={
                        "Origin": self.settings.base_url,
                        "x-neon-auth-middleware": "true",
                    },
                    params=params,
                    json=body,
                )
            if response.status_code >= 500 or response.status_code == 429:
                raise ProviderUnavailable()
            return response
        except httpx.HTTPError:
            raise ProviderUnavailable() from None

    async def get_session(self, cookies):
        if not session_cookies(cookies):
            return None, None
        response = await self.call(
            "get-session", cookies=cookies, params={"disableCookieCache": "true"}
        )
        if response.status_code != 200:
            return None, response
        try:
            return verified_identity(response.json()), response
        except ValueError:
            raise ProviderUnavailable() from None
