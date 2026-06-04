from datetime import date
from typing import Iterable

from app.models.availability import Availability

WEEKEND_AVAILABLE = "WEEKEND_AVAILABLE"


def build_availability_sets(
    items: Iterable[Availability],
) -> tuple[set[tuple[int, date]], set[tuple[int, date]]]:
    unavailable_dates: set[tuple[int, date]] = set()
    weekend_available_dates: set[tuple[int, date]] = set()

    for item in items:
        key = (item.person_id, item.date)
        if item.type == WEEKEND_AVAILABLE:
            weekend_available_dates.add(key)
        else:
            unavailable_dates.add(key)

    return unavailable_dates, weekend_available_dates


def is_person_available(
    person_id: int,
    day: date,
    unavailable_dates: set[tuple[int, date]],
    weekend_available_dates: set[tuple[int, date]],
) -> bool:
    key = (person_id, day)

    if day.weekday() >= 5:
        return key in weekend_available_dates

    return key not in unavailable_dates
