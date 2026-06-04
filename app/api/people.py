from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.availability import Availability
from app.models.guard_assignment import GuardAssignment
from app.models.person import Person

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SORT_OPTIONS = {
    "name_asc": func.lower(Person.full_name).asc(),
    "name_desc": func.lower(Person.full_name).desc(),
}


def normalize_sort(sort: str) -> str:
    return sort if sort in SORT_OPTIONS else "name_asc"


def people_redirect(sort: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/personas?sort={normalize_sort(sort)}",
        status_code=303,
    )


@router.get("/personas")
def list_people(
    request: Request,
    sort: str = Query(default="name_asc"),
    db: Session = Depends(get_db),
):
    selected_sort = normalize_sort(sort)
    people = db.query(Person).order_by(SORT_OPTIONS[selected_sort], Person.id).all()

    return templates.TemplateResponse(
        request=request,
        name="personas.html",
        context={
            "people": people,
            "selected_sort": selected_sort,
        },
    )


@router.post("/personas")
def create_person(
    full_name: str = Form(...),
    notes: str = Form(""),
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    full_name = full_name.strip()
    notes = notes.strip()

    if not full_name:
        return people_redirect(sort)

    person = Person(
        full_name=full_name,
        notes=notes or None,
        active=True,
    )

    db.add(person)
    db.commit()

    return people_redirect(sort)


@router.post("/personas/{person_id}/desactivar")
def deactivate_person(
    person_id: int,
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()

    if person:
        person.active = False
        db.commit()

    return people_redirect(sort)


@router.post("/personas/{person_id}/eliminar")
def delete_person(
    person_id: int,
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()

    if person:
        db.query(Availability).filter(
            Availability.person_id == person_id,
        ).delete(synchronize_session=False)
        db.query(GuardAssignment).filter(
            GuardAssignment.person_id == person_id,
        ).delete(synchronize_session=False)
        db.delete(person)
        db.commit()

    return people_redirect(sort)


@router.post("/personas/{person_id}/activar")
def activate_person(
    person_id: int,
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()

    if person:
        person.active = True
        db.commit()

    return people_redirect(sort)
