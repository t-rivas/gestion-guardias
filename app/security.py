import hashlib
import hmac
import os
import secrets
from urllib.parse import urlencode, urlsplit
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from app.models import Account
from app.web import templates
from app.auth_config import local_path
from app.services.neon_auth import ProviderUnavailable, apply_cookies


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 600_000
    ).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password, encoded):
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 600_000
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def auth_tag(account):
    return hashlib.sha256(account.password_hash.encode()).hexdigest()


def error_response(request, status, message):
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"message": message, "status": status},
        status_code=status,
    )


class AccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.session.setdefault("csrf", secrets.token_urlsafe(32))
        response = await self.protected_dispatch(request, call_next)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = (
            "no-referrer" if request.url.path == "/auth/callback" else "same-origin"
        )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return response

    async def protected_dispatch(self, request: Request, call_next):
        path = request.url.path
        settings = request.app.state.auth_settings
        request.state.authenticated = False
        upstream = None
        if request.method in {"GET", "HEAD"} and (
            path.startswith("/static/") or path == "/health"
        ):
            return await call_next(request)
        if settings.mode == "neon":
            if path == "/setup":
                return error_response(
                    request, 404, "El acceso se configura por correo."
                )
            if path == "/webhooks/neon-auth" and request.method == "POST":
                # This endpoint verifies its own signature, timestamp and event envelope.
                return await call_next(request)
            public = (
                path == "/login"
                or (path == "/auth/callback" and request.method == "GET")
                or (path == "/logout" and request.method == "POST")
            )
            if not public:
                try:
                    user, upstream = await request.app.state.neon_auth.get_session(
                        request.cookies
                    )
                except ProviderUnavailable:
                    return error_response(
                        request,
                        503,
                        "No se pudo verificar el acceso. Volvé a intentarlo.",
                    )
                if not user:
                    if request.method not in {"GET", "HEAD"} or path.startswith(
                        "/calendario/exportar/"
                    ):
                        return error_response(request, 401, "Ingresá para continuar.")
                    destination = local_path(
                        path + ("?" + request.url.query if request.url.query else "")
                    )
                    return RedirectResponse(
                        "/login?" + urlencode({"next": destination}), status_code=303
                    )
                request.state.authenticated = True
                request.state.user = user
        else:
            with request.app.state.session_factory() as db:
                account = db.get(Account, 1)
            if not account and path not in {"/setup"}:
                return RedirectResponse("/setup", status_code=303)
            if account and path == "/setup":
                return RedirectResponse("/login", status_code=303)
            authenticated = (
                account
                and request.session.get("account_id") == account.id
                and hmac.compare_digest(
                    request.session.get("auth_tag", ""), auth_tag(account)
                )
            )
            if account and not authenticated and path != "/login":
                return RedirectResponse("/login", status_code=303)
            request.state.authenticated = bool(authenticated)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            origin_value = origin or referer
            if origin_value:
                parsed = urlsplit(origin_value)
                actual = f"{parsed.scheme}://{parsed.netloc}"
                allowed = (
                    {settings.base_url}
                    if settings.mode == "neon"
                    else {str(request.base_url).rstrip("/")}
                ) | {
                    value.strip()
                    for value in os.getenv("TRUSTED_ORIGINS", "").split(",")
                    if value.strip()
                }
                if actual not in allowed:
                    return error_response(
                        request, 403, "La solicitud proviene de otro sitio."
                    )
            try:
                length = int(request.headers.get("content-length", "0") or 0)
            except ValueError:
                return error_response(request, 400, "La solicitud no es válida.")
            if length > 2_000_000:
                return error_response(request, 413, "La solicitud es demasiado grande.")
            if len(await request.body()) > 2_000_000:
                return error_response(request, 413, "La solicitud es demasiado grande.")
            form = await request.form()
            token = form.get("csrf_token", "")
            if not isinstance(token, str) or not hmac.compare_digest(
                token, request.session["csrf"]
            ):
                return error_response(
                    request,
                    403,
                    "La sesión venció. Recargá la página y volvé a intentarlo.",
                )
        response = await call_next(request)
        if upstream is not None:
            apply_cookies(response, upstream)
        return response
