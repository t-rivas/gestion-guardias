import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect


def migrate(engine):
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def legacy(engine, duplicates=False):
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE people (id INTEGER PRIMARY KEY, full_name VARCHAR(200) NOT NULL, active BOOLEAN, notes VARCHAR(500))"
            )
        )
        c.execute(text("INSERT INTO people VALUES (1,'Preserved',1,'Note')"))
        c.execute(
            text(
                "CREATE TABLE availability (id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES people(id), date DATE NOT NULL, type VARCHAR(50) NOT NULL)"
            )
        )
        c.execute(text("INSERT INTO availability VALUES (1,1,'2026-03-02','OTHER')"))
        if duplicates:
            c.execute(
                text("INSERT INTO availability VALUES (2,1,'2026-03-02','OTHER')")
            )
        c.execute(
            text(
                "CREATE TABLE guard_assignments (id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES people(id), date DATE NOT NULL, CONSTRAINT uq_guard_assignments_date UNIQUE (date))"
            )
        )
        c.execute(text("INSERT INTO guard_assignments VALUES (1,1,'2026-03-03')"))


def test_fresh_migration_and_idempotency():
    e = create_engine("sqlite://")
    migrate(e)
    migrate(e)
    assert {
        "accounts",
        "schedule_versions",
        "planning_state",
        "auth_deliveries",
        "auth_rate_limits",
        "role_availability",
    } <= set(inspect(e).get_table_names())
    with e.connect() as c:
        assert (
            c.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0004"
        )


def test_existing_data_preserved():
    e = create_engine("sqlite://")
    legacy(e)
    migrate(e)
    with e.connect() as c:
        assert c.execute(text("SELECT full_name FROM people")).scalar() == "Preserved"
        assert c.execute(text("SELECT COUNT(*) FROM availability")).scalar() == 1
        assert c.execute(text("SELECT slot FROM guard_assignments")).scalar() == 1
        assert c.execute(text("SELECT locked FROM guard_assignments")).scalar() == 0


def test_duplicates_stop_without_deleting_records():
    e = create_engine("sqlite://")
    legacy(e, True)
    with pytest.raises(RuntimeError, match="No records were deleted"):
        migrate(e)
    with e.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM availability")).scalar() == 2
