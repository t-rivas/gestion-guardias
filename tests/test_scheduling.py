from collections import Counter
from datetime import date
from random import Random
from app.models import Availability, GuardAssignment, Person
from app.services.availability_rules import build_availability_sets, is_person_available
from app.services.schedule_generator import generate_monthly_schedule
from app.services.planning import replace_month, lock_state


def people(db, n):
    result = [Person(full_name=f"Person {i}") for i in range(n)]
    db.add_all(result)
    db.commit()
    return result


def test_cross_month_weekly_limit(db):
    team = people(db, 14)
    for day in (date(2026, 9, 28), date(2026, 9, 29)):
        for slot, p in enumerate(team[:4], 1):
            db.add(
                GuardAssignment(
                    person_id=p.id,
                    date=day,
                    slot=slot,
                    role="substitute" if slot == 4 else "primary",
                )
            )
    for p in team:
        for day in (date(2026, 10, 3), date(2026, 10, 4)):
            db.add(Availability(person_id=p.id, date=day, type="AVAILABLE"))
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 10, Random(0))
    counts = Counter(a.person_id for a in db.query(GuardAssignment).all())
    counts.update(r["person_id"] for r in rows if r["date"] <= "2026-10-04")
    assert max(counts.values()) <= 2
    assert len([r for r in rows if r["date"] <= "2026-10-04"]) == 16
    assert db.query(GuardAssignment).count() == 8  # draft generation never overwrites


def test_scarce_availability_has_complete_feasible_coverage(db):
    team = people(db, 8)
    for idx, p in enumerate(team):
        for d in range(1, 32):
            day = date(2026, 3, d)
            allowed = d in (2, 3, 4) if idx < 4 else d == 2
            if day.weekday() < 5 and not allowed:
                db.add(Availability(person_id=p.id, date=day, type="OTHER"))
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(0))
    assert Counter(r["date"] for r in rows) == {
        "2026-03-02": 4,
        "2026-03-03": 4,
        "2026-03-04": 4,
    }


def test_locked_assignment_survives_and_counts_toward_capacity(db):
    team = people(db, 14)
    db.add(
        GuardAssignment(
            person_id=team[0].id,
            date=date(2026, 3, 2),
            slot=4,
            role="substitute",
            locked=True,
        )
    )
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(1))
    assert {
        "person_id": team[0].id,
        "date": "2026-03-02",
        "slot": 4,
        "role": "substitute",
        "locked": True,
    } in rows
    counts = Counter(
        (date.fromisoformat(r["date"]).isocalendar()[:2], r["person_id"]) for r in rows
    )
    assert max(counts.values()) <= 2
    assert len({(r["date"], r["person_id"]) for r in rows}) == len(rows)


def test_recurring_rule_and_explicit_override(db):
    team = people(db, 1)
    p = team[0]
    p.blocked_weekdays = "4"
    db.commit()
    friday = date(2026, 3, 6)
    assert not is_person_available(p.id, friday, set(), set(), {p.id: p.blocked_days})
    db.add(Availability(person_id=p.id, date=friday, type="AVAILABLE"))
    db.commit()
    unavailable, available = build_availability_sets(db.query(Availability).all())
    assert is_person_available(
        p.id, friday, unavailable, available, {p.id: p.blocked_days}
    )


def test_year_boundaries_and_empty_team(db):
    assert generate_monthly_schedule(db, 1, 1, Random(0)) == []
    assert generate_monthly_schedule(db, 9999, 12, Random(0)) == []


def test_rest_improvement_preserves_capacity_and_availability():
    from app.services.schedule_generator import improve_rest

    selected = {
        date(2026, 3, 2): {1},
        date(2026, 3, 3): {1},
        date(2026, 3, 4): {2},
        date(2026, 3, 5): {2},
    }
    edges = {(day, pid): None for day in selected for pid in (1, 2)}
    result = improve_rest(selected, edges, {})
    assert all(len(ids) == 1 for ids in result.values())
    assert Counter(pid for ids in result.values() for pid in ids) == {1: 2, 2: 2}
    ordered = list(result.values())
    assert sum(bool(a & b) for a, b in zip(ordered, ordered[1:])) == 0


def test_postgresql_serializes_racing_saves(factory):
    import pytest
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from fastapi import HTTPException

    with factory() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("PostgreSQL row-lock integration")
    acquired = Event()
    release = Event()

    def first():
        with factory() as db:
            state = lock_state(db, 0)
            acquired.set()
            assert release.wait(10)
            db.add(Person(full_name="First writer"))
            state.revision += 1
            db.commit()

    def second():
        with factory() as db:
            assert acquired.wait(10)
            try:
                lock_state(db, 0)
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(first)
        loser = executor.submit(second)
        assert acquired.wait(10)
        release.set()
        winner.result(timeout=10)
        assert loser.result(timeout=10) == 409
    with factory() as db:
        assert db.query(Person).count() == 1
