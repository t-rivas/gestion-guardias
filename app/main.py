from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.availability import router as availability_router
from app.api.calendar import router as calendar_router
from app.api.people import router as people_router
from app.db.base import Base
from app.db.database import engine
from app.models.availability import Availability
from app.models.guard_assignment import GuardAssignment
from app.models.person import Person

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(people_router)
app.include_router(availability_router)
app.include_router(calendar_router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
    )
