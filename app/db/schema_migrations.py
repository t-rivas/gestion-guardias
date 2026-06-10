from sqlalchemy import text
from sqlalchemy.engine import Engine


def migrate_guard_assignments_schema(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE guard_assignments "
                "DROP CONSTRAINT IF EXISTS uq_guard_assignments_date"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE guard_assignments "
                "ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'primary'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE guard_assignments "
                "ADD COLUMN IF NOT EXISTS slot INTEGER NOT NULL DEFAULT 1"
            )
        )
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_guard_assignments_date_slot'
                    ) THEN
                        ALTER TABLE guard_assignments
                        ADD CONSTRAINT uq_guard_assignments_date_slot
                        UNIQUE (date, slot);
                    END IF;
                END
                $$;
                """
            )
        )
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_guard_assignments_date_person'
                    ) THEN
                        ALTER TABLE guard_assignments
                        ADD CONSTRAINT uq_guard_assignments_date_person
                        UNIQUE (date, person_id);
                    END IF;
                END
                $$;
                """
            )
        )
