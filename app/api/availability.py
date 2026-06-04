import calendar
import json
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.availability import Availability
from app.models.person import Person
from app.services.availability_rules import WEEKEND_AVAILABLE
from app.services.availability_rules import build_availability_sets

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)

WEEKDAY_NAMES = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


@router.get("/disponibilidad")
def availability_page(
    request: Request,
    year: int | None = Query(default=None, ge=1, le=9999),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    today = date.today()
    selected_year = year or today.year
    selected_month = month or today.month

    people = db.query(Person).filter(Person.active == True).order_by(Person.id).all()

    _, total_days = calendar.monthrange(selected_year, selected_month)
    days = [date(selected_year, selected_month, day) for day in range(1, total_days + 1)]

    unavailable = db.query(Availability).filter(
        Availability.date >= days[0],
        Availability.date <= days[-1],
    ).all()

    unavailable_dates, weekend_available_dates = build_availability_sets(unavailable)

    return templates.TemplateResponse(
        request=request,
        name="disponibilidad.html",
        context={
            "people": people,
            "days": days,
            "year": selected_year,
            "month": selected_month,
            "month_name": MONTH_NAMES[selected_month - 1],
            "month_options": enumerate(MONTH_NAMES, start=1),
            "weekday_names": WEEKDAY_NAMES,
            "unavailable_dates": unavailable_dates,
            "weekend_available_dates": weekend_available_dates,
            "previous_year": selected_year - 1 if selected_month == 1 else selected_year,
            "previous_month": 12 if selected_month == 1 else selected_month - 1,
            "next_year": selected_year + 1 if selected_month == 12 else selected_year,
            "next_month": 1 if selected_month == 12 else selected_month + 1,
        },
    )


@router.post("/disponibilidad/toggle")
def toggle_availability(
    person_id: int = Form(...),
    day: str = Form(...),
    reason: str = Form("OTHER"),
    db: Session = Depends(get_db),
):
    selected_day = date.fromisoformat(day)

    existing = db.query(Availability).filter(
        Availability.person_id == person_id,
        Availability.date == selected_day,
    ).all()

    if selected_day.weekday() >= 5:
        weekend_override = next(
            (item for item in existing if item.type == WEEKEND_AVAILABLE),
            None,
        )

        for item in existing:
            db.delete(item)

        if weekend_override is None:
            db.add(
                Availability(
                    person_id=person_id,
                    date=selected_day,
                    type=WEEKEND_AVAILABLE,
                )
            )
    else:
        if existing:
            for item in existing:
                db.delete(item)
        else:
            db.add(
                Availability(
                    person_id=person_id,
                    date=selected_day,
                    type=reason,
                )
            )

    db.commit()

    return RedirectResponse(
        url=f"/disponibilidad?year={selected_day.year}&month={selected_day.month}",
        status_code=303,
    )


@router.post("/disponibilidad/guardar")
def save_availability(
    year: int = Form(..., ge=1, le=9999),
    month: int = Form(..., ge=1, le=12),
    changes: str = Form("[]"),
    db: Session = Depends(get_db),
):
    try:
        submitted_changes = json.loads(changes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Cambios inválidos") from exc

    if not isinstance(submitted_changes, list):
        raise HTTPException(status_code=400, detail="Cambios inválidos")

    active_person_ids = {
        person_id
        for person_id, in db.query(Person.id).filter(Person.active.is_(True)).all()
    }

    for change in submitted_changes:
        if not isinstance(change, dict):
            raise HTTPException(status_code=400, detail="Cambio inválido")

        person_id = change.get("person_id")
        day_value = change.get("day")
        is_available = change.get("available")

        if (
            not isinstance(person_id, int)
            or person_id not in active_person_ids
            or not isinstance(day_value, str)
            or not isinstance(is_available, bool)
        ):
            raise HTTPException(status_code=400, detail="Cambio inválido")

        try:
            selected_day = date.fromisoformat(day_value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Fecha inválida") from exc

        if selected_day.year != year or selected_day.month != month:
            raise HTTPException(status_code=400, detail="Fecha fuera del mes seleccionado")

        db.query(Availability).filter(
            Availability.person_id == person_id,
            Availability.date == selected_day,
        ).delete(synchronize_session=False)

        if selected_day.weekday() >= 5 and is_available:
            db.add(
                Availability(
                    person_id=person_id,
                    date=selected_day,
                    type=WEEKEND_AVAILABLE,
                )
            )
        elif selected_day.weekday() < 5 and not is_available:
            db.add(
                Availability(
                    person_id=person_id,
                    date=selected_day,
                    type="OTHER",
                )
            )

    db.commit()

    return RedirectResponse(
        url=f"/disponibilidad?year={year}&month={month}",
        status_code=303,
    )
