import calendar
from collections import Counter
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import (
    Availability,
    GuardAssignment,
    Person,
    PlanningState,
    ScheduleVersion,
)
from app.services.availability_rules import is_person_available, load_role_availability

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


def month_days(year, month):
    return [
        date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)
    ]


def shift_day(day, delta):
    return date.fromordinal(max(1, min(date.max.toordinal(), day.toordinal() + delta)))


def week_bounds(days):
    return shift_day(days[0], -days[0].weekday()), shift_day(
        days[-1], 6 - days[-1].weekday()
    )


def month_context(year, month):
    previous = (year - 1, 12) if month == 1 else (year, month - 1)
    following = (year + 1, 1) if month == 12 else (year, month + 1)
    return dict(
        year=year,
        month=month,
        month_name=MONTH_NAMES[month - 1],
        month_options=list(enumerate(MONTH_NAMES, 1)),
        weekday_names=WEEKDAY_NAMES,
        previous_year=previous[0],
        previous_month=previous[1],
        next_year=following[0],
        next_month=following[1],
        has_previous=previous[0] >= 1,
        has_next=following[0] <= 9999,
    )


def lock_state(db: Session, expected: int | None = None):
    state = db.execute(
        select(PlanningState).where(PlanningState.id == 1).with_for_update()
    ).scalar_one()
    if expected is not None and expected != state.revision:
        raise HTTPException(
            409,
            "Los datos cambiaron en otra sesión. Recargá la página antes de guardar.",
        )
    return state


def serialize(assignments):
    return [
        dict(
            person_id=a.person_id,
            date=a.date.isoformat(),
            role=a.role,
            slot=a.slot,
            locked=a.locked,
        )
        for a in assignments
    ]


def saved_month(db, year, month):
    days = month_days(year, month)
    return (
        db.query(GuardAssignment)
        .filter(GuardAssignment.date.between(days[0], days[-1]))
        .order_by(GuardAssignment.date, GuardAssignment.slot)
        .all()
    )


def snapshot(db, year, month, state, label):
    db.add(
        ScheduleVersion(
            year=year,
            month=month,
            kind="snapshot",
            label=label[:200],
            assignments=serialize(saved_month(db, year, month)),
            base_revision=state.revision,
        )
    )


def validate_schedule(db, year, month, rows, allow_existing_conflicts=False):
    days = month_days(year, month)
    start, end = week_bounds(days)
    people = {p.id: p for p in db.query(Person).all()}
    blocked = {pid: p.blocked_days for pid, p in people.items()}
    role_availability = load_role_availability(db, days[0], days[-1])
    adjacent = (
        db.query(GuardAssignment)
        .filter(
            GuardAssignment.date.between(start, end),
            ~GuardAssignment.date.between(days[0], days[-1]),
        )
        .all()
    )
    current = (
        serialize(saved_month(db, year, month)) if allow_existing_conflicts else []
    )
    weekly = Counter((a.date.isocalendar()[:2], a.person_id) for a in adjacent)
    for row in rows:
        weekly[
            (date.fromisoformat(row["date"]).isocalendar()[:2], row["person_id"])
        ] += 1
    slots, person_days = set(), set()
    for row in rows:
        day = date.fromisoformat(row["date"])
        pid, slot = row["person_id"], row["slot"]
        person = people.get(pid)
        if (
            day not in days
            or slot not in range(1, 5)
            or row["role"] != ("substitute" if slot == 4 else "primary")
        ):
            raise HTTPException(400, "Asignación inválida.")
        if (day, slot) in slots or (day, pid) in person_days:
            raise HTTPException(
                409, "Una persona no puede ocupar dos lugares el mismo día."
            )
        slots.add((day, slot))
        person_days.add((day, pid))
        # Editing one conflict must not require fixing every unrelated conflict first.
        unchanged = row in current
        if not unchanged and (
            not person
            or not person.active
            or not is_person_available(
                pid, day, *role_availability[row["role"]], blocked
            )
        ):
            raise HTTPException(
                409,
                "Hay una persona inactiva, eliminada o no disponible. Revisá las asignaciones.",
            )
        if not unchanged and weekly[(day.isocalendar()[:2], pid)] > 2:
            raise HTTPException(
                409,
                "Se supera el máximo de dos asignaciones por persona en una semana.",
            )


def replace_month(db, year, month, rows, state, label, allow_existing_conflicts=False):
    validate_schedule(db, year, month, rows, allow_existing_conflicts)
    snapshot(db, year, month, state, label)
    days = month_days(year, month)
    db.query(GuardAssignment).filter(
        GuardAssignment.date.between(days[0], days[-1])
    ).delete(synchronize_session="fetch")
    db.flush()
    for row in rows:
        db.add(
            GuardAssignment(
                person_id=row["person_id"],
                date=date.fromisoformat(row["date"]),
                role=row["role"],
                slot=row["slot"],
                locked=row.get("locked", False),
            )
        )
    state.revision += 1
    db.commit()


def schedule_view(db, year, month, rows=None):
    days = month_days(year, month)
    saved = saved_month(db, year, month)
    rows = serialize(saved) if rows is None else rows
    people = {p.id: p for p in db.query(Person).order_by(Person.full_name).all()}
    blocked = {pid: p.blocked_days for pid, p in people.items()}
    role_availability = load_role_availability(db, days[0], days[-1])
    start, end = week_bounds(days)
    adjacent = (
        db.query(GuardAssignment)
        .filter(
            GuardAssignment.date.between(start, end),
            ~GuardAssignment.date.between(days[0], days[-1]),
        )
        .all()
    )
    weekly = Counter((a.date.isocalendar()[:2], a.person_id) for a in adjacent)
    for row in rows:
        day = date.fromisoformat(row["date"])
        weekly[(day.isocalendar()[:2], row["person_id"])] += 1
    schedule, conflicts = [], []
    for day in days:
        entries = []
        for slot in range(1, 5):
            row = next(
                (r for r in rows if r["date"] == day.isoformat() and r["slot"] == slot),
                None,
            )
            person = people.get(row["person_id"]) if row else None
            conflict = bool(
                row
                and (
                    not person
                    or not person.active
                    or not is_person_available(
                        person.id, day, *role_availability[row["role"]], blocked
                    )
                    or weekly[(day.isocalendar()[:2], person.id)] > 2
                )
            )
            entry = dict(slot=slot, row=row, person=person, conflict=conflict)
            entries.append(entry)
            if conflict:
                conflicts.append(entry)
        schedule.append(
            dict(
                day=day,
                entries=entries,
                missing=sum(e["row"] is None for e in entries),
                conflict=any(e["conflict"] for e in entries),
            )
        )
    summaries = [
        dict(
            person=p,
            primary_count=sum(
                r["person_id"] == p.id and r["role"] == "primary" for r in rows
            ),
            substitute_count=sum(
                r["person_id"] == p.id and r["role"] == "substitute" for r in rows
            ),
        )
        for p in people.values()
        if p.active or any(r["person_id"] == p.id for r in rows)
    ]
    return dict(
        schedule=schedule,
        person_summaries=summaries,
        people=[p for p in people.values() if p.active],
        missing_slots=sum(d["missing"] for d in schedule),
        conflict_count=len(conflicts),
        has_assignments=bool(rows),
        rows=rows,
        **month_context(year, month)
    )
