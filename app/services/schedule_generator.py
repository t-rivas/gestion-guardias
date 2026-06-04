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

    assignment_counts: Counter[int] = Counter()
    previous_person_id: int | None = None
    unassigned_days: list[date] = []

    for day in days:
        candidates = [
            person
            for person in people
            if is_person_available(
                person.id,
                day,
                unavailable_dates,
                weekend_available_dates,
            )
        ]

        if not candidates:
            unassigned_days.append(day)
            previous_person_id = None
            continue

        non_consecutive_candidates = [
            person
            for person in candidates
            if person.id != previous_person_id
        ]
        if non_consecutive_candidates:
            candidates = non_consecutive_candidates

        minimum_assignments = min(
            assignment_counts[person.id]
            for person in candidates
        )
        balanced_candidates = [
            person
            for person in candidates
            if assignment_counts[person.id] == minimum_assignments
        ]
        selected_person = rng.choice(balanced_candidates)

        db.add(
            GuardAssignment(
                person_id=selected_person.id,
                date=day,
            )
        )
        assignment_counts[selected_person.id] += 1
        previous_person_id = selected_person.id

    db.commit()

    return unassigned_days
