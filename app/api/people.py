from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import (
    Availability,
    GuardAssignment,
    Person,
    PlanningState,
    RoleAvailability,
)
from app.services.planning import WEEKDAY_NAMES, lock_state, snapshot
from app.web import templates

router = APIRouter()
SORT_OPTIONS = {
    "name_asc": func.lower(Person.full_name).asc(),
    "name_desc": func.lower(Person.full_name).desc(),
}


def normalize_sort(sort):
    return sort if sort in SORT_OPTIONS else "name_asc"


def people_redirect(sort):
    return RedirectResponse(f"/personas?sort={normalize_sort(sort)}", status_code=303)


def person_values(full_name, notes, blocked_weekdays):
    full_name, notes = full_name.strip(), notes.strip()
    if not full_name:
        raise HTTPException(400, "Ingresá un nombre completo.")
    if any(day not in range(7) for day in blocked_weekdays):
        raise HTTPException(400, "Día de la semana inválido.")
    return dict(
        full_name=full_name,
        notes=notes or None,
        blocked_weekdays=",".join(str(d) for d in sorted(set(blocked_weekdays))),
    )


def require_person(db, person_id):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(404, "Persona no encontrada.")
    return person


@router.get("/personas")
def list_people(
    request: Request, sort: str = Query("name_asc"), db: Session = Depends(get_db)
):
    sort = normalize_sort(sort)
    people = db.query(Person).order_by(SORT_OPTIONS[sort], Person.id).all()
    return templates.TemplateResponse(
        request=request,
        name="personas.html",
        context=dict(
            people=people,
            selected_sort=sort,
            weekday_names=WEEKDAY_NAMES,
            revision=db.get(PlanningState, 1).revision,
        ),
    )


@router.post("/personas")
def create_person(
    full_name: str = Form(..., max_length=200),
    notes: str = Form("", max_length=500),
    blocked_weekdays: list[int] = Form([]),
    sort: str = Form("name_asc"),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    db.add(Person(**person_values(full_name, notes, blocked_weekdays), active=True))
    state.revision += 1
    db.commit()
    return people_redirect(sort)


@router.post("/personas/{person_id}/editar")
def edit_person(
    person_id: int,
    full_name: str = Form(..., max_length=200),
    notes: str = Form("", max_length=500),
    blocked_weekdays: list[int] = Form([]),
    sort: str = Form("name_asc"),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    person = require_person(db, person_id)
    for field, value in person_values(full_name, notes, blocked_weekdays).items():
        setattr(person, field, value)
    state.revision += 1
    db.commit()
    return people_redirect(sort)


@router.post("/personas/{person_id}/desactivar")
def deactivate_person(
    person_id: int,
    revision: int = Form(...),
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    require_person(db, person_id).active = False
    state.revision += 1
    db.commit()
    return people_redirect(sort)


@router.post("/personas/{person_id}/activar")
def activate_person(
    person_id: int,
    revision: int = Form(...),
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    require_person(db, person_id).active = True
    state.revision += 1
    db.commit()
    return people_redirect(sort)


@router.post("/personas/{person_id}/eliminar")
def delete_person(
    person_id: int,
    revision: int = Form(...),
    sort: str = Form("name_asc"),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    person = require_person(db, person_id)
    months = {
        (a.date.year, a.date.month)
        for a in db.query(GuardAssignment).filter_by(person_id=person_id).all()
    }
    for year, month in months:
        snapshot(db, year, month, state, f"Antes de eliminar a {person.full_name}")
    db.query(RoleAvailability).filter_by(person_id=person_id).delete(
        synchronize_session=False
    )
    db.query(Availability).filter_by(person_id=person_id).delete(
        synchronize_session=False
    )
    db.query(GuardAssignment).filter_by(person_id=person_id).delete(
        synchronize_session=False
    )
    db.delete(person)
    state.revision += 1
    db.commit()
    return people_redirect(sort)
