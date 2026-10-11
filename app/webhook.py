"""Vercel entrypoint for a separate deployment exposing only signed delivery."""

from fastapi import FastAPI

from app.api.auth_webhook import router
from app.auth_config import AuthSettings, email_origins
from app.db.database import SessionLocal
from app.services.auth_webhooks import WebhookVerifier
from app.services.neon_auth import NeonAuth


def create_webhook_app(settings=None, session_factory=None):
    settings = settings or AuthSettings.from_env()
    if settings.mode != "neon":
        raise RuntimeError("The delivery-only deployment requires Neon authentication.")
    email_origins(settings)  # Reject malformed routing configuration before serving.
    app = FastAPI(
        docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False
    )
    app.state.auth_settings = settings
    app.state.session_factory = session_factory or SessionLocal
    app.state.neon_auth = NeonAuth(settings)
    app.state.webhook_verifier = WebhookVerifier(app.state.neon_auth)
    app.include_router(router)

    @app.middleware("http")
    async def private_delivery_response(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    return app


app = create_webhook_app()
