import calendar
from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.availability import MONTH_NAMES, WEEKDAY_NAMES
from app.db.database import get_db
from app.models.availability import Availability
from app.models.guard_assignment import GuardAssignment
from app.models.person import Person
from app.services.availability_rules import build_availability_sets
from app.services.availability_rules import is_person_available
from app.services.schedule_generator import generate_monthly_schedule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/calendario")
def calendar_page(
    request: Request,
    year: int | None = Query(default=None, ge=1, le=9999),
    month: int | None = Query(default=None, ge=1, le=12),
    generated: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    today = date.today()
    selected_year = year or today.year
    selected_month = month or today.month

    _, total_days = calendar.monthrange(selected_year, selected_month)
    days = [
        date(selected_year, selected_month, day)
        for day in range(1, total_days + 1)
    ]

    assignments = (
        db.query(GuardAssignment, Person)
        .join(Person, Person.id == GuardAssignment.person_id)
        .filter(
            GuardAssignment.date >= days[0],
            GuardAssignment.date <= days[-1],
        )
        .order_by(GuardAssignment.date)
        .all()
    )
    assignment_by_date = {
        assignment.date: person
        for assignment, person in assignments
    }

    unavailable = (
        db.query(Availability)
        .filter(
            Availability.date >= days[0],
            Availability.date <= days[-1],
        )
        .all()
    )
    unavailable_dates, weekend_available_dates = build_availability_sets(unavailable)

    schedule = [
        {
            "day": day,
            "person": assignment_by_date.get(day),
            "has_conflict": (
                assignment_by_date.get(day) is not None
                and (
                    not assignment_by_date[day].active
                    or not is_person_available(
                        assignment_by_date[day].id,
                        day,
                        unavailable_dates,
                        weekend_available_dates,
                    )
                )
            ),
        }
        for day in days
    ]
    unassigned_days = [
        item["day"]
        for item in schedule
        if item["person"] is None
    ]
    conflict_days = [
        item["day"]
        for item in schedule
        if item["has_conflict"]
    ]

    assignment_counts = Counter(
        person.id
        for _, person in assignments
    )
    assigned_people = {
        person.id: person
        for _, person in assignments
    }
    people = (
        db.query(Person)
        .filter(Person.active.is_(True))
        .order_by(Person.full_name)
        .all()
    )
    people_by_id = {
        person.id: person
        for person in people
    }
    people_by_id.update(assigned_people)
    person_summaries = [
        {
            "person": person,
            "count": assignment_counts[person.id],
        }
        for person in sorted(
            people_by_id.values(),
            key=lambda person: person.full_name.lower(),
        )
    ]

    return templates.TemplateResponse(
        request=request,
        name="calendario.html",
        context={
            "schedule": schedule,
            "person_summaries": person_summaries,
            "has_assignments": bool(assignments),
            "unassigned_days": unassigned_days,
            "conflict_days": conflict_days,
            "generated": generated,
            "year": selected_year,
            "month": selected_month,
            "month_name": MONTH_NAMES[selected_month - 1],
            "month_options": enumerate(MONTH_NAMES, start=1),
            "weekday_names": WEEKDAY_NAMES,
            "previous_year": selected_year - 1 if selected_month == 1 else selected_year,
            "previous_month": 12 if selected_month == 1 else selected_month - 1,
            "next_year": selected_year + 1 if selected_month == 12 else selected_year,
            "next_month": 1 if selected_month == 12 else selected_month + 1,
        },
    )


@router.post("/calendario/generar")
def generate_calendar(
    year: int = Form(..., ge=1, le=9999),
    month: int = Form(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    generate_monthly_schedule(
        db=db,
        year=year,
        month=month,
    )

    return RedirectResponse(
        url=f"/calendario?year={year}&month={month}&generated=true",
        status_code=303,
    )
