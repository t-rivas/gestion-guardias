"""Signed webhook route shared by the app and the delivery-only deployment."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.services.auth_webhooks import InvalidWebhook, deliver_event
from app.services.neon_auth import ProviderUnavailable

router = APIRouter()


@router.post("/webhooks/neon-auth")
async def webhook(request: Request):
    if request.app.state.auth_settings.mode != "neon":
        raise HTTPException(404)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413)
    raw = bytes(raw)
    try:
        data = await request.app.state.webhook_verifier.verify(raw, request.headers)
        kwargs = {}
        if hasattr(request.app.state, "email_sender"):
            kwargs["sender"] = request.app.state.email_sender
        status, body = await run_in_threadpool(
            deliver_event,
            data,
            raw,
            request.app.state.auth_settings,
            request.app.state.session_factory,
            **kwargs,
        )
        return JSONResponse(body, status_code=status)
    except InvalidWebhook:
        raise HTTPException(400, "Webhook no válido.") from None
    except ProviderUnavailable:
        raise HTTPException(503, "No se pudo verificar el webhook.") from None
