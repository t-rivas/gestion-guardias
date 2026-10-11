import json
from datetime import date
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import Availability, Person, PlanningState, RoleAvailability
from app.services.availability_rules import (
    ROLES,
    ROLE_LABELS,
    build_availability_sets,
    is_person_available,
    load_role_availability,
    set_role_availability,
)
from app.services.planning import (
    MONTH_NAMES,
    WEEKDAY_NAMES,
    lock_state,
    month_context,
    month_days,
)
from app.web import templates

router = APIRouter()


def set_availability(db, person, day, available):
    # Legacy callers update both roles; their old contract remains supported.
    db.query(RoleAvailability).filter_by(person_id=person.id, date=day).delete(
        synchronize_session=False
    )
    default = day.weekday() < 5 and day.weekday() not in person.blocked_days
    existing = (
        db.query(Availability).filter_by(person_id=person.id, date=day).one_or_none()
    )
    if available == default:
        if existing:
            db.delete(existing)
    elif existing:
        existing.type = "AVAILABLE" if available else "OTHER"
    else:
        db.add(
            Availability(
                person_id=person.id,
                date=day,
                type="AVAILABLE" if available else "OTHER",
            )
        )


@router.get("/disponibilidad")
def availability_page(
    request: Request,
    year: int | None = Query(None, ge=1, le=9999),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    today = date.today()
    year, month = year or today.year, month or today.month
    days = month_days(year, month)
    people = (
        db.query(Person)
        .filter(Person.active.is_(True))
        .order_by(Person.full_name)
        .all()
    )
    role_availability = load_role_availability(db, days[0], days[-1])
    blocked = {p.id: p.blocked_days for p in people}
    values = {
        (p.id, d, role): is_person_available(p.id, d, *role_availability[role], blocked)
        for p in people
        for d in days
        for role in ROLES
    }
    return templates.TemplateResponse(
        request=request,
        name="disponibilidad.html",
        context=dict(
            people=people,
            days=days,
            availability_values=values,
            roles=ROLES,
            role_labels=ROLE_LABELS,
            revision=db.get(PlanningState, 1).revision,
            **month_context(year, month),
        ),
    )


@router.post("/disponibilidad/toggle")
def toggle_availability(
    person_id: int = Form(...),
    day: date = Form(...),
    role: str = Form("both"),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    person = db.get(Person, person_id)
    if not person or not person.active:
        raise HTTPException(404, "Persona activa no encontrada.")
    if role not in (*ROLES, "both"):
        raise HTTPException(400, "Rol inválido.")
    if role == "both":
        unavailable, available = build_availability_sets(
            db.query(Availability).filter_by(person_id=person_id, date=day).all()
        )
        set_availability(
            db,
            person,
            day,
            not is_person_available(
                person_id, day, unavailable, available, {person_id: person.blocked_days}
            ),
        )
    else:
        role_availability = load_role_availability(db, day, day)
        value = not is_person_available(
            person_id, day, *role_availability[role], {person_id: person.blocked_days}
        )
        set_role_availability(db, person_id, day, role, value)
    state.revision += 1
    db.commit()
    return RedirectResponse(
        f"/disponibilidad?year={day.year}&month={day.month}", status_code=303
    )


@router.post("/disponibilidad/guardar")
def save_availability(
    year: int = Form(..., ge=1, le=9999),
    month: int = Form(..., ge=1, le=12),
    changes: str = Form("[]", max_length=1_500_000),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        submitted = json.loads(changes)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, "Cambios inválidos.") from exc
    if not isinstance(submitted, list) or len(submitted) > 20_000:
        raise HTTPException(400, "Cambios inválidos o demasiados cambios.")
    state = lock_state(db, revision)
    people = {p.id: p for p in db.query(Person).filter(Person.active.is_(True)).all()}
    parsed = {}
    for change in submitted:
        if (
            not isinstance(change, dict)
            or type(change.get("person_id")) is not int
            or change["person_id"] not in people
            or type(change.get("available")) is not bool
        ):
            raise HTTPException(400, "Cambio inválido.")
        try:
            day = date.fromisoformat(change["day"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, "Fecha inválida.") from exc
        if (day.year, day.month) != (year, month):
            raise HTTPException(400, "Fecha fuera del mes seleccionado.")
        role = change.get("role", "both")
        if role not in (*ROLES, "both"):
            raise HTTPException(400, "Rol inválido.")
        # Expand to individual role keys so repeated/mixed changes have a predictable last value.
        for target in ROLES if role == "both" else (role,):
            parsed[(change["person_id"], day, target)] = change["available"]
    general_keys = {
        (change["person_id"], date.fromisoformat(change["day"]))
        for change in submitted
        if change.get("role", "both") == "both"
    }
    for pid, day in general_keys:
        if parsed[(pid, day, "primary")] == parsed[(pid, day, "substitute")]:
            set_availability(db, people[pid], day, parsed.pop((pid, day, "primary")))
            parsed.pop((pid, day, "substitute"))
    for (pid, day, role), available in parsed.items():
        set_role_availability(db, pid, day, role, available)
    if submitted:
        state.revision += 1
    db.commit()
    return RedirectResponse(
        f"/disponibilidad?year={year}&month={month}&saved=true", status_code=303
    )
