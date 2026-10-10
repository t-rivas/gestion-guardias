from datetime import date
from typing import Iterable
from app.models.availability import Availability

WEEKEND_AVAILABLE = "WEEKEND_AVAILABLE"
EXPLICIT_AVAILABLE = "AVAILABLE"


def build_availability_sets(items: Iterable[Availability]) -> tuple[set, set]:
    unavailable, available = set(), set()
    for item in items:
        (
            available
            if item.type in {WEEKEND_AVAILABLE, EXPLICIT_AVAILABLE}
            else unavailable
        ).add((item.person_id, item.date))
    return unavailable, available


def is_person_available(
    person_id: int,
    day: date,
    unavailable_dates: set,
    weekend_available_dates: set,
    blocked_weekdays: dict | None = None,
) -> bool:
    key = (person_id, day)
    if key in unavailable_dates:
        return False
    if key in weekend_available_dates:
        return True
    return day.weekday() < 5 and day.weekday() not in (blocked_weekdays or {}).get(
        person_id, set()
    )


ROLES = ("primary", "substitute")
ROLE_LABELS = {"primary": "Guardia principal", "substitute": "Suplente"}


def build_role_availability_sets(items, overrides):
    unavailable, available = build_availability_sets(items)
    result = {role: (set(unavailable), set(available)) for role in ROLES}
    for override in overrides:
        blocked, allowed = result[override.role]
        key = (override.person_id, override.date)
        blocked.discard(key)
        allowed.discard(key)
        (allowed if override.available else blocked).add(key)
    return result


def load_role_availability(db, first_day, last_day):
    from app.models.role_availability import RoleAvailability

    items = (
        db.query(Availability)
        .filter(Availability.date.between(first_day, last_day))
        .all()
    )
    overrides = (
        db.query(RoleAvailability)
        .filter(RoleAvailability.date.between(first_day, last_day))
        .all()
    )
    return build_role_availability_sets(items, overrides)


def set_role_availability(db, person_id, day, role, available):
    from app.models.role_availability import RoleAvailability

    if role not in ROLES:
        raise ValueError("Invalid assignment role")
    existing = (
        db.query(RoleAvailability)
        .filter_by(person_id=person_id, date=day, role=role)
        .one_or_none()
    )
    if existing:
        existing.available = available
    else:
        db.add(
            RoleAvailability(
                person_id=person_id, date=day, role=role, available=available
            )
        )
