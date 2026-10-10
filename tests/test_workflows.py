import json
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import (
    Availability,
    GuardAssignment,
    Person,
    PlanningState,
    ScheduleVersion,
)
from app.api.calendar import fold_ics, ics_escape, safe_csv
from tests.conftest import token, revision


def post(client, path, values, page="/personas"):
    response = client.get(page)
    return client.post(
        path,
        data={"csrf_token": token(response), "revision": revision(response), **values},
    )


def add(client, name="María", **extras):
    assert (
        post(
            client, "/personas", {"full_name": name, "notes": "", **extras}
        ).status_code
        == 200
    )


def test_account_setup_login_and_security(client):
    assert (
        client.get("/personas", follow_redirects=False).headers["location"] == "/setup"
    )
    setup = client.get("/setup")
    csrf = token(setup)
    assert (
        client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/setup",
            data={
                "csrf_token": csrf,
                "username": "admin",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/setup",
            data={
                "csrf_token": csrf,
                "username": "admin",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        ).status_code
        == 200
    )
    csrf = token(client.get("/personas"))
    assert (
        client.post(
            "/logout", data={"csrf_token": csrf}, follow_redirects=False
        ).headers["location"]
        == "/login"
    )
    assert (
        client.get("/personas", follow_redirects=False).headers["location"] == "/login"
    )
    csrf = token(client.get("/login"))
    assert (
        client.post(
            "/login",
            data={"csrf_token": csrf, "username": "admin", "password": "wrong"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/login",
            data={
                "csrf_token": csrf,
                "username": "admin",
                "password": "test-password-123",
            },
        ).status_code
        == 200
    )
    assert client.post("/personas", data={"full_name": "No token"}).status_code == 403
    assert client.get("/health").json() == {"status": "ok"}


def test_person_validation_edit_and_stale_save(signed_client, db):
    c = signed_client
    add(c)
    p = db.query(Person).one()
    assert (
        post(
            c,
            f"/personas/{p.id}/editar",
            {"full_name": "María López", "notes": "Info", "blocked_weekdays": [4]},
        ).status_code
        == 200
    )
    db.expire_all()
    assert db.get(Person, p.id).blocked_days == {4}
    assert post(c, "/personas", {"full_name": "x" * 201}).status_code == 422
    assert post(c, "/personas", {"full_name": " "}).status_code == 400
    stale = c.get("/personas")
    add(c, "Otro")
    assert (
        c.post(
            "/personas",
            data={
                "csrf_token": token(stale),
                "revision": revision(stale),
                "full_name": "Stale",
            },
        ).status_code
        == 409
    )
    assert db.query(Person).count() == 2


def test_availability_validation_atomic_and_uniqueness(signed_client, db):
    c = signed_client
    add(c)
    p = db.query(Person).one()
    page = "/disponibilidad?year=2026&month=3"
    assert (
        post(
            c, "/disponibilidad/toggle", {"person_id": p.id, "day": "not-a-date"}, page
        ).status_code
        == 422
    )
    changes = [
        {"person_id": p.id, "day": "2026-03-02", "available": False},
        {"person_id": p.id, "day": "2026-04-02", "available": False},
    ]
    assert (
        post(
            c,
            "/disponibilidad/guardar",
            {"year": 2026, "month": 3, "changes": json.dumps(changes)},
            page,
        ).status_code
        == 400
    )
    assert db.query(Availability).count() == 0
    changes = changes[:1]
    assert (
        post(
            c,
            "/disponibilidad/guardar",
            {"year": 2026, "month": 3, "changes": json.dumps(changes + changes)},
            page,
        ).status_code
        == 200
    )
    assert db.query(Availability).count() == 1
    db.add(
        Availability(
            person_id=p.id, date=db.query(Availability).one().date, type="OTHER"
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_draft_apply_history_restore_stale_and_edit(signed_client, db):
    c = signed_client
    for i in range(8):
        add(c, f"Person {i}")
    page = "/calendario?year=2026&month=3"
    assert (
        post(c, "/calendario/generar", {"year": 2026, "month": 3}, page).status_code
        == 200
    )
    draft = db.query(ScheduleVersion).filter_by(kind="draft").one()
    assert db.query(GuardAssignment).count() == 0
    assert (
        post(c, f"/calendario/versiones/{draft.id}/aplicar", {}, page).status_code
        == 200
    )
    assert db.query(GuardAssignment).count() > 0
    old = db.query(ScheduleVersion).filter_by(kind="snapshot").one()
    assert old.assignments == []
    row = db.query(GuardAssignment).first()
    edited_day, edited_slot = row.date, row.slot
    assert (
        post(
            c,
            "/calendario/editar",
            {
                "day": row.date.isoformat(),
                "slot": row.slot,
                "person_id": row.person_id,
                "locked": "true",
            },
            page,
        ).status_code
        == 200
    )
    db.expire_all()
    assert (
        db.query(GuardAssignment)
        .filter_by(date=edited_day, slot=edited_slot)
        .one()
        .locked
    )

    assert (
        post(c, "/calendario/generar", {"year": 2026, "month": 3}, page).status_code
        == 200
    )
    newest = (
        db.query(ScheduleVersion)
        .filter_by(kind="draft")
        .order_by(ScheduleVersion.id.desc())
        .first()
    )
    assert any(r["locked"] for r in newest.assignments)
    add(c, "New person")
    assert (
        post(c, f"/calendario/versiones/{newest.id}/aplicar", {}, page).status_code
        == 409
    )
    assert (
        post(c, f"/calendario/versiones/{old.id}/aplicar", {}, page).status_code == 200
    )
    assert db.query(GuardAssignment).count() == 0


def test_manual_edits_swaps_exports(signed_client, db):
    c = signed_client
    add(c, "=SUM(1,2)")
    add(c, "José, Sánchez; Médico")
    ids = [p.id for p in db.query(Person).order_by(Person.id).all()]
    page = "/calendario?year=2026&month=3"
    for slot, pid in enumerate(ids, 1):
        assert (
            post(
                c,
                "/calendario/editar",
                {"day": "2026-03-02", "slot": slot, "person_id": pid},
                page,
            ).status_code
            == 200
        )
    assert (
        post(
            c,
            "/calendario/intercambiar",
            {
                "year": 2026,
                "month": 3,
                "first": "2026-03-02:1",
                "second": "2026-03-02:2",
            },
            page,
        ).status_code
        == 200
    )
    assert (
        post(
            c,
            "/calendario/editar",
            {"day": "2026-03-02", "slot": 3, "person_id": ids[0]},
            page,
        ).status_code
        == 409
    )
    assert db.query(GuardAssignment).count() == 2
    assert (
        post(
            c,
            "/calendario/editar",
            {"day": "2026-03-02", "slot": 1, "person_id": ids[1], "locked": "true"},
            page,
        ).status_code
        == 200
    )
    assert (
        post(
            c,
            "/calendario/intercambiar",
            {
                "year": 2026,
                "month": 3,
                "first": "2026-03-02:1",
                "second": "2026-03-02:2",
            },
            page,
        ).status_code
        == 409
    )
    csv = c.get("/calendario/exportar/csv?year=2026&month=3")
    assert csv.status_code == 200 and "'=SUM" in csv.text
    ics = c.get("/calendario/exportar/ics?year=2026&month=3")
    assert ics.status_code == 200 and "BEGIN:VCALENDAR" in ics.text
    assert "José\\, Sánchez\\; Médico" in ics.text
    assert "DTSTART;VALUE=DATE:20260302" in ics.text
    assert all(len(line.encode()) <= 75 for line in ics.text.split("\r\n"))


def test_export_helpers():
    assert safe_csv(" @cmd") == "' @cmd"
    assert all(
        len(line.encode()) <= 75
        for line in fold_ics("SUMMARY:" + "á" * 100).split("\r\n")
    )


def test_conflicts_can_be_fixed_individually(signed_client, db):
    c = signed_client
    for name in ("A", "B", "C", "D"):
        add(c, name)
    people = db.query(Person).order_by(Person.id).all()
    page = "/calendario?year=2026&month=3"
    for slot, person in enumerate(people[:2], 1):
        assert (
            post(
                c,
                "/calendario/editar",
                {"day": "2026-03-02", "slot": slot, "person_id": person.id},
                page,
            ).status_code
            == 200
        )
    assert post(c, f"/personas/{people[0].id}/desactivar", {}).status_code == 200
    assert post(c, f"/personas/{people[1].id}/desactivar", {}).status_code == 200
    assert (
        post(
            c,
            "/calendario/editar",
            {"day": "2026-03-02", "slot": 1, "person_id": people[2].id},
            page,
        ).status_code
        == 200
    )
    assert (
        post(
            c,
            "/calendario/editar",
            {"day": "2026-03-02", "slot": 2, "person_id": people[3].id},
            page,
        ).status_code
        == 200
    )
