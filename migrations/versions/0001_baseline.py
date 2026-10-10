"""Adopt existing databases and create the baseline for fresh installations."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "people" not in tables:
        op.create_table(
            "people",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("full_name", sa.String(200), nullable=False),
            sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.String(500)),
        )
    if "availability" not in tables:
        op.create_table(
            "availability",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "person_id", sa.Integer, sa.ForeignKey("people.id"), nullable=False
            ),
            sa.Column("date", sa.Date, nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
        )
    if "guard_assignments" not in tables:
        op.create_table(
            "guard_assignments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "person_id", sa.Integer, sa.ForeignKey("people.id"), nullable=False
            ),
            sa.Column("date", sa.Date, nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="primary"),
            sa.Column("slot", sa.Integer, nullable=False, server_default="1"),
            sa.UniqueConstraint("date", "slot", name="uq_guard_assignments_date_slot"),
            sa.UniqueConstraint(
                "date", "person_id", name="uq_guard_assignments_date_person"
            ),
        )
    else:
        columns = {c["name"] for c in sa.inspect(bind).get_columns("guard_assignments")}
        constraints = {
            c["name"]
            for c in sa.inspect(bind).get_unique_constraints("guard_assignments")
        }
        with op.batch_alter_table("guard_assignments") as batch:
            if "uq_guard_assignments_date" in constraints:
                batch.drop_constraint("uq_guard_assignments_date", type_="unique")
            if "role" not in columns:
                batch.add_column(
                    sa.Column(
                        "role", sa.String(20), nullable=False, server_default="primary"
                    )
                )
            if "slot" not in columns:
                batch.add_column(
                    sa.Column("slot", sa.Integer, nullable=False, server_default="1")
                )
            if "uq_guard_assignments_date_slot" not in constraints:
                batch.create_unique_constraint(
                    "uq_guard_assignments_date_slot", ["date", "slot"]
                )
            if "uq_guard_assignments_date_person" not in constraints:
                batch.create_unique_constraint(
                    "uq_guard_assignments_date_person", ["date", "person_id"]
                )
    if "ix_guard_assignments_date" not in {
        i["name"] for i in sa.inspect(bind).get_indexes("guard_assignments")
    }:
        op.create_index("ix_guard_assignments_date", "guard_assignments", ["date"])


def downgrade():
    raise RuntimeError(
        "Baseline downgrade would delete existing data; restore a backup instead."
    )
