"""Availability integrity, recurring rules, locks, history, and access accounts."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT person_id, date FROM availability GROUP BY person_id, date HAVING COUNT(*) > 1"
            )
        )
        .first()
    )
    if duplicates:
        raise RuntimeError(
            "Duplicate availability records found. No records were deleted. Reconcile duplicates after taking a backup, then retry the migration."
        )
    with op.batch_alter_table("availability") as batch:
        batch.create_unique_constraint(
            "uq_availability_person_date", ["person_id", "date"]
        )
        batch.create_index("ix_availability_date", ["date"])
    with op.batch_alter_table("people") as batch:
        batch.add_column(
            sa.Column(
                "blocked_weekdays", sa.String(20), nullable=False, server_default=""
            )
        )
    with op.batch_alter_table("guard_assignments") as batch:
        batch.add_column(
            sa.Column("locked", sa.Boolean, nullable=False, server_default=sa.false())
        )
        batch.create_check_constraint(
            "ck_assignment_role_slot",
            "(slot BETWEEN 1 AND 3 AND role = 'primary') OR (slot = 4 AND role = 'substitute')",
        )
    op.create_table(
        "planning_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("revision", sa.Integer, nullable=False),
    )
    op.execute(sa.text("INSERT INTO planning_state (id, revision) VALUES (1, 0)"))
    op.create_table(
        "schedule_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("assignments", sa.JSON, nullable=False),
        sa.Column("base_revision", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
    )


def downgrade():
    raise RuntimeError(
        "This revision contains account and history data; restore a backup instead."
    )
