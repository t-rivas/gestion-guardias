import calendar
import random
from collections import Counter
from datetime import date
from random import Random

from sqlalchemy.orm import Session

from app.models.availability import Availability
from app.models.guard_assignment import GuardAssignment
from app.models.person import Person
from app.services.availability_rules import build_availability_sets
from app.services.availability_rules import is_person_available

ASSIGNMENT_SLOTS = (
    ("primary", 1),
    ("primary", 2),
    ("primary", 3),
    ("substitute", 4),
)
MAX_WEEKLY_ASSIGNMENTS = 2


def generate_monthly_schedule(
    db: Session,
    year: int,
    month: int,
    rng: Random | None = None,
) -> list[date]:
    rng = rng or random.SystemRandom()
    _, total_days = calendar.monthrange(year, month)
    days = [date(year, month, day) for day in range(1, total_days + 1)]

    people = (
        db.query(Person)
        .filter(Person.active.is_(True))
        .order_by(Person.id)
        .all()
    )

    unavailable = (
        db.query(Availability)
        .filter(
            Availability.date >= days[0],
            Availability.date <= days[-1],
        )
        .all()
    )
    unavailable_dates, weekend_available_dates = build_availability_sets(unavailable)

    db.query(GuardAssignment).filter(
        GuardAssignment.date >= days[0],
        GuardAssignment.date <= days[-1],
    ).delete(synchronize_session="fetch")

    monthly_assignment_counts: Counter[int] = Counter()
    weekly_assignment_counts: Counter[tuple[int, int, int]] = Counter()
    previous_day_person_ids: set[int] = set()
    unassigned_days: list[date] = []

    for day in days:
        selected_person_ids: set[int] = set()
        week_year, week_number, _ = day.isocalendar()
        missing_assignment = False

        for role, slot in ASSIGNMENT_SLOTS:
            candidates = [
                person
                for person in people
                if (
                    person.id not in selected_person_ids
                    and weekly_assignment_counts[
                        (week_year, week_number, person.id)
                    ] < MAX_WEEKLY_ASSIGNMENTS
                    and is_person_available(
                        person.id,
                        day,
                        unavailable_dates,
                        weekend_available_dates,
                    )
                )
            ]

            if not candidates:
                missing_assignment = True
                continue

            non_consecutive_candidates = [
                person
                for person in candidates
                if person.id not in previous_day_person_ids
            ]
            if non_consecutive_candidates:
                candidates = non_consecutive_candidates

            minimum_monthly_assignments = min(
                monthly_assignment_counts[person.id]
                for person in candidates
            )
            balanced_candidates = [
                person
                for person in candidates
                if monthly_assignment_counts[person.id] == minimum_monthly_assignments
            ]
            selected_person = rng.choice(balanced_candidates)

            db.add(
                GuardAssignment(
                    person_id=selected_person.id,
                    date=day,
                    role=role,
                    slot=slot,
                )
            )
            selected_person_ids.add(selected_person.id)
            monthly_assignment_counts[selected_person.id] += 1
            weekly_key = (week_year, week_number, selected_person.id)
            weekly_assignment_counts[weekly_key] += 1

        if missing_assignment:
            unassigned_days.append(day)
        previous_day_person_ids = selected_person_ids

    db.commit()

    return unassigned_days
