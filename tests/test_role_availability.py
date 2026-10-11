import json
from collections import Counter
from datetime import date
from random import Random
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.models import (
    Availability,
    GuardAssignment,
    Person,
    RoleAvailability,
    ScheduleVersion,
)
from app.services.availability_rules import (
    build_role_availability_sets,
    is_person_available,
    load_role_availability,
    set_role_availability,
)
from app.services.planning import schedule_view, validate_schedule
from app.services.schedule_generator import generate_monthly_schedule
from tests.test_workflows import add, post


def team_with_one_day(db, count):
    people = [Person(full_name=f"Person {i}") for i in range(count)]
    db.add_all(people)
    db.commit()
    for person in people:
        for number in range(1, 32):
            day = date(2026, 3, number)
            if day.weekday() < 5:
                db.add(Availability(person_id=person.id, date=day, type="OTHER"))
    db.commit()
    return people


def test_exact_role_eligibility_and_no_double_booking(db):
    people = team_with_one_day(db, 4)
    day = date(2026, 3, 2)
    for person in people[:3]:
        set_role_availability(db, person.id, day, "primary", True)
    set_role_availability(db, people[3].id, day, "substitute", True)
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(0))
    assert len(rows) == 4
    assert {r["person_id"] for r in rows if r["role"] == "primary"} == {
        p.id for p in people[:3]
    }
    assert {r["person_id"] for r in rows if r["role"] == "substitute"} == {people[3].id}
    assert all(r["date"] == day.isoformat() for r in rows)
    assert len({(r["date"], r["person_id"]) for r in rows}) == 4


def test_substitute_only_day_does_not_become_a_main_guard(db):
    person = team_with_one_day(db, 1)[0]
    set_role_availability(db, person.id, date(2026, 3, 2), "substitute", True)
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(0))
    assert rows == [
        {
            "person_id": person.id,
            "date": "2026-03-02",
            "slot": 4,
            "role": "substitute",
            "locked": False,
        }
    ]


def test_shared_daily_capacity_when_both_roles_selected(db):
    person = team_with_one_day(db, 1)[0]
    for role in ("primary", "substitute"):
        set_role_availability(db, person.id, date(2026, 3, 2), role, True)
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(0))
    assert len(rows) == 1 and rows[0]["role"] == "primary"


def test_role_scarcity_reconsiders_early_choices(db):
    people = team_with_one_day(db, 8)
    for i, person in enumerate(people):
        for number in (2, 3, 4) if i < 4 else (2,):
            role = "substitute" if i % 4 == 3 else "primary"
            set_role_availability(db, person.id, date(2026, 3, number), role, True)
    db.commit()
    rows = generate_monthly_schedule(db, 2026, 3, Random(0))
    assert Counter(r["date"] for r in rows) == {
        "2026-03-02": 4,
        "2026-03-03": 4,
        "2026-03-04": 4,
    }
    assert max(Counter(r["person_id"] for r in rows).values()) <= 2


def test_role_edits_are_independent_and_make_drafts_stale(signed_client, db):
    client = signed_client
    add(client, "Person")
    person = db.query(Person).one()
    page = "/disponibilidad?year=2026&month=3"
    changes = [
        {
            "person_id": person.id,
            "day": "2026-03-02",
            "role": "primary",
            "available": False,
        },
        {
            "person_id": person.id,
            "day": "2026-03-03",
            "role": "substitute",
            "available": False,
        },
    ]
    assert (
        post(
            client,
            "/disponibilidad/guardar",
            {"year": 2026, "month": 3, "changes": json.dumps(changes)},
            page,
        ).status_code
        == 200
    )
    availability = load_role_availability(db, date(2026, 3, 1), date(2026, 3, 31))
    assert not is_person_available(
        person.id, date(2026, 3, 2), *availability["primary"]
    )
    assert is_person_available(person.id, date(2026, 3, 2), *availability["substitute"])
    assert is_person_available(person.id, date(2026, 3, 3), *availability["primary"])
    assert not is_person_available(
        person.id, date(2026, 3, 3), *availability["substitute"]
    )
    calendar = "/calendario?year=2026&month=3"
    assert (
        post(
            client, "/calendario/generar", {"year": 2026, "month": 3}, calendar
        ).status_code
        == 200
    )
    draft = db.query(ScheduleVersion).filter_by(kind="draft").one()
    assert (
        post(
            client,
            "/disponibilidad/toggle",
            {"person_id": person.id, "day": "2026-03-04", "role": "substitute"},
            page,
        ).status_code
        == 200
    )
    assert (
        post(
            client, f"/calendario/versiones/{draft.id}/aplicar", {}, calendar
        ).status_code
        == 409
    )


def test_role_validation_rejects_swaps_and_restore_with_wrong_role(signed_client, db):
    client = signed_client
    add(client, "Person")
    person = db.query(Person).one()
    page = "/calendario?year=2026&month=3"
    set_role_availability(db, person.id, date(2026, 3, 2), "primary", False)
    db.commit()
    assert (
        post(
            client,
            "/calendario/editar",
            {"person_id": person.id, "day": "2026-03-02", "slot": 1},
            page,
        ).status_code
        == 409
    )
    assert (
        post(
            client,
            "/calendario/editar",
            {"person_id": person.id, "day": "2026-03-02", "slot": 4},
            page,
        ).status_code
        == 200
    )
    row = {
        "person_id": person.id,
        "date": "2026-03-02",
        "slot": 1,
        "role": "primary",
        "locked": False,
    }
    with pytest.raises(HTTPException):
        validate_schedule(db, 2026, 3, [row])
    db.add(
        ScheduleVersion(
            year=2026,
            month=3,
            kind="snapshot",
            label="Old primary assignment",
            assignments=[row],
            base_revision=0,
        )
    )
    db.commit()
    version = db.query(ScheduleVersion).filter_by(label="Old primary assignment").one()
    assert (
        post(
            client, f"/calendario/versiones/{version.id}/aplicar", {}, page
        ).status_code
        == 409
    )


def test_existing_schedule_conflict_tracks_the_assigned_role(db):
    person = team_with_one_day(db, 1)[0]
    day = date(2026, 3, 2)
    set_role_availability(db, person.id, day, "substitute", True)
    db.add(GuardAssignment(person_id=person.id, date=day, role="substitute", slot=4))
    db.commit()
    assert schedule_view(db, 2026, 3)["conflict_count"] == 0
    set_role_availability(db, person.id, day, "substitute", False)
    db.commit()
    assert schedule_view(db, 2026, 3)["conflict_count"] == 1


def test_invalid_role_changes_are_atomic(signed_client, db):
    client = signed_client
    add(client, "Person")
    person = db.query(Person).one()
    changes = [
        {
            "person_id": person.id,
            "day": "2026-03-02",
            "role": "primary",
            "available": False,
        },
        {
            "person_id": person.id,
            "day": "2026-03-03",
            "role": "wrong",
            "available": True,
        },
    ]
    assert (
        post(
            client,
            "/disponibilidad/guardar",
            {"year": 2026, "month": 3, "changes": json.dumps(changes)},
            "/disponibilidad?year=2026&month=3",
        ).status_code
        == 400
    )
    assert db.query(RoleAvailability).count() == 0


def test_role_overrides_are_unique(db):
    person = team_with_one_day(db, 1)[0]
    day = date(2026, 3, 2)
    set_role_availability(db, person.id, day, "primary", True)
    db.commit()
    db.add(
        RoleAvailability(person_id=person.id, date=day, role="primary", available=False)
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_legacy_weekend_and_unavailability_preserved(db):
    person = Person(full_name="Legacy", blocked_weekdays="4")
    db.add(person)
    db.commit()
    db.add_all(
        [
            Availability(person_id=person.id, date=date(2026, 3, 2), type="OTHER"),
            Availability(
                person_id=person.id, date=date(2026, 3, 7), type="WEEKEND_AVAILABLE"
            ),
        ]
    )
    db.commit()
    by_role = load_role_availability(db, date(2026, 3, 1), date(2026, 3, 31))
    for role in ("primary", "substitute"):
        assert not is_person_available(
            person.id,
            date(2026, 3, 2),
            *by_role[role],
            {person.id: person.blocked_days},
        )
        assert is_person_available(
            person.id,
            date(2026, 3, 7),
            *by_role[role],
            {person.id: person.blocked_days},
        )
        assert not is_person_available(
            person.id,
            date(2026, 3, 6),
            *by_role[role],
            {person.id: person.blocked_days},
        )
