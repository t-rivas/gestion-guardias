import os
import logging
import secrets
from urllib.parse import urlencode, urlsplit
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import Account, PlanningState
from app.security import auth_tag, password_hash, verify_password
from app.web import templates
from app.auth_config import allowed_emails, local_path, normalized_email
from app.services.auth_storage import take_rate_limit
from app.services.neon_auth import (
    ProviderUnavailable,
    SESSION_COOKIE,
    apply_cookies,
    response_cookies,
)
from app.api.auth_webhook import router as webhook_router

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/setup")
def setup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        context={"setup": True, "username": "admin", "error": None},
    )


@router.post("/setup")
def setup(
    request: Request,
    username: str = Form(..., min_length=1, max_length=100),
    password: str = Form(..., min_length=12, max_length=200),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="auth.html",
            context={
                "setup": True,
                "username": username,
                "error": "Las contraseñas no coinciden.",
            },
            status_code=400,
        )
    # Serialize first-run setup and reject racing attempts to replace the account.
    db.execute(
        select(PlanningState).where(PlanningState.id == 1).with_for_update()
    ).scalar_one()
    if db.get(Account, 1):
        raise HTTPException(409, "La cuenta ya está configurada.")
    if not username.strip():
        raise HTTPException(400, "Ingresá un nombre de usuario.")
    account = Account(
        id=1, username=username.strip(), password_hash=password_hash(password)
    )
    db.add(account)
    db.commit()
    request.session.clear()
    request.session.update(
        account_id=account.id,
        auth_tag=auth_tag(account),
        csrf=secrets.token_urlsafe(32),
    )
    return RedirectResponse("/", status_code=303)


@router.get("/login")
def login_page(request: Request):
    settings = request.app.state.auth_settings
    if settings.mode == "neon":
        # Render the form on the configured origin so its cookie, CSRF token and
        # provider callback all belong to the same site, including preview links.
        if request.url.netloc.lower() != urlsplit(settings.base_url).netloc.lower():
            query = {}
            if "next" in request.query_params:
                query["next"] = local_path(request.query_params["next"])
            if request.query_params.get("error"):
                query["error"] = "expired"
            target = settings.base_url + "/login"
            if query:
                target += "?" + urlencode(query)
            return RedirectResponse(target, status_code=303)
        return magic_page(
            request,
            error=(
                "El enlace venció o ya se usó. Solicitá uno nuevo."
                if request.query_params.get("error")
                else None
            ),
        )
    return templates.TemplateResponse(
        request=request,
        name="auth.html",
        context={"setup": False, "username": "", "error": None},
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form("", max_length=100),
    password: str = Form("", max_length=200),
    email: str = Form("", max_length=254),
    next: str = Form("/", max_length=2000),
    db: Session = Depends(get_db),
):
    if request.app.state.auth_settings.mode == "neon":
        return await request_link(request, email, next)
    account = db.get(Account, 1)
    # Run the password check even for an incorrect username.
    valid = account and verify_password(password, account.password_hash)
    if not valid or username != account.username:
        return templates.TemplateResponse(
            request=request,
            name="auth.html",
            context={
                "setup": False,
                "username": username,
                "error": "Usuario o contraseña incorrectos.",
            },
            status_code=401,
        )
    request.session.clear()
    request.session.update(
        account_id=account.id,
        auth_tag=auth_tag(account),
        csrf=secrets.token_urlsafe(32),
    )
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    if request.app.state.auth_settings.mode == "neon":
        try:
            upstream = await request.app.state.neon_auth.call(
                "sign-out", "POST", cookies=request.cookies, body={}
            )
        except ProviderUnavailable:
            raise HTTPException(
                503, "No se pudo cerrar la sesión. Volvé a intentarlo."
            ) from None
        if upstream.status_code not in {200, 204, 401}:
            raise HTTPException(503, "No se pudo cerrar la sesión. Volvé a intentarlo.")
        request.session.clear()
        response = RedirectResponse("/login", status_code=303)
        apply_cookies(response, upstream)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
        )
        return response
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def magic_page(request, *, sent=False, error=None, destination=None):
    return templates.TemplateResponse(
        request=request,
        name="magic_login.html",
        context={
            "sent": sent,
            "error": error,
            "destination": local_path(destination or request.query_params.get("next")),
        },
    )


async def request_link(request, email, destination):
    settings = request.app.state.auth_settings
    # A global delivery outage must not appear as a successful email request.
    # Apply this check equally to every address to preserve the allowlist policy.
    sender_configured = callable(getattr(request.app.state, "email_sender", None)) or (
        all(
            os.getenv(name, "").strip()
            for name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
        )
        and os.getenv("SMTP_SECURITY", "starttls") in {"starttls", "ssl"}
    )
    if not sender_configured:
        response = magic_page(
            request,
            error="El envío de enlaces no está disponible por el momento. Volvé a intentarlo más tarde.",
            destination=destination,
        )
        response.status_code = 503
        return response
    email = normalized_email(email)
    destination = local_path(destination)
    secret = os.environ["SESSION_SECRET"]
    with request.app.state.session_factory() as db:
        requester = request.client.host if request.client else "unknown"
        limited = not take_rate_limit(
            db, "requester", requester, secret, limit=10, seconds=600
        )
        limited = not take_rate_limit(db, "request-email", email, secret) or limited
    if email in allowed_emails() and not limited:
        try:
            await request.app.state.neon_auth.call(
                "sign-in/magic-link",
                "POST",
                body={
                    "email": email,
                    "callbackURL": settings.base_url + destination,
                    "errorCallbackURL": settings.base_url + "/login?error=expired",
                },
            )
        except ProviderUnavailable:
            # Same observable response for denied addresses, provider errors and cooldown.
            pass
    response = magic_page(request, sent=True, destination=destination)
    response.headers["Retry-After"] = "60"
    return response


@router.get("/auth/callback")
async def callback(request: Request):
    if request.app.state.auth_settings.mode != "neon":
        raise HTTPException(404)
    token = request.query_params.get("token", "")
    if not token or len(token) > 1024:
        return RedirectResponse("/login?error=expired", status_code=303)
    destination = local_path(request.query_params.get("next"))
    with request.app.state.session_factory() as db:
        if not take_rate_limit(
            db,
            "callback",
            request.client.host if request.client else "unknown",
            os.environ["SESSION_SECRET"],
            limit=15,
            seconds=60,
        ):
            raise HTTPException(429, "Esperá un minuto y volvé a intentarlo.")
    settings = request.app.state.auth_settings
    provider = request.app.state.neon_auth
    try:
        upstream = await provider.call(
            "magic-link/verify",
            params={
                "token": token,
                "callbackURL": settings.base_url + destination,
                "errorCallbackURL": settings.base_url + "/login?error=expired",
            },
        )
        if upstream.status_code not in {200, 302, 303}:
            logger.warning("Neon callback rejected: verification HTTP %s", upstream.status_code)
            return RedirectResponse("/login?error=expired", status_code=303)
        # Never forward an upstream redirect. Validate the actual resulting session.
        cookies = response_cookies(upstream)
        user, session_response = await provider.get_session(cookies)
        if not user:
            logger.warning(
                "Neon callback rejected: session_cookie=%s set_cookie_count=%s session_http=%s",
                bool(cookies), len(upstream.headers.get_list("set-cookie")),
                session_response.status_code if session_response is not None else None,
            )
            return RedirectResponse("/login?error=expired", status_code=303)
    except ProviderUnavailable:
        raise HTTPException(
            503, "No se pudo verificar el enlace. Solicitá uno nuevo más tarde."
        ) from None
    request.session.clear()
    request.session["csrf"] = secrets.token_urlsafe(32)
    response = RedirectResponse(destination, status_code=303)
    apply_cookies(response, upstream)
    if session_response is not None:
        apply_cookies(response, session_response)
    return response


router.include_router(webhook_router)
