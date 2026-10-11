import os
import secrets
from datetime import date
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from app.api.auth import router as auth_router
from app.api.availability import router as availability_router
from app.api.calendar import router as calendar_router
from app.api.people import router as people_router
from app.db.database import SessionLocal, get_db
from app.models import Person
from app.security import AccessMiddleware, error_response
from app.services.planning import schedule_view
from app.web import templates
from app.auth_config import AuthSettings
from app.services.neon_auth import NeonAuth
from app.services.auth_webhooks import WebhookVerifier

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.state.session_factory = SessionLocal
app.state.auth_settings = AuthSettings.from_env()
app.state.neon_auth = NeonAuth(app.state.auth_settings)
app.state.webhook_verifier = WebhookVerifier(app.state.neon_auth)
app.add_middleware(AccessMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(48),
    same_site="lax",
    https_only=app.state.auth_settings.secure,
    max_age=8 * 60 * 60,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
for router in (auth_router, people_router, availability_router, calendar_router):
    app.include_router(router)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error_response(request, exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    labels = {
        "full_name": "nombre",
        "notes": "observaciones",
        "blocked_weekdays": "restricciones semanales",
        "person_id": "persona",
        "year": "año",
        "month": "mes",
        "day": "fecha",
        "slot": "lugar",
        "revision": "versión de la página",
        "changes": "disponibilidad",
        "username": "usuario",
        "password": "contraseña",
        "confirm_password": "confirmación de contraseña",
    }
    fields = ", ".join(
        dict.fromkeys(
            labels.get(str(error["loc"][-1]), "datos") for error in exc.errors()
        )
    )
    return error_response(
        request,
        422,
        f"Revisá los datos del formulario ({fields}). Verificá fechas, campos obligatorios y longitudes máximas.",
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return error_response(
        request,
        409,
        "Los datos cambiaron mientras guardabas. Recargá la página y volvé a intentarlo.",
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    context = schedule_view(db, today.year, today.month)
    context["active_people"] = db.query(Person).filter(Person.active.is_(True)).count()
    return templates.TemplateResponse(
        request=request, name="home.html", context=context
    )
