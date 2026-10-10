"""Add independent main-guard and substitute days without changing legacy records."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "role_availability",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("person_id", sa.Integer, sa.ForeignKey("people.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("available", sa.Boolean, nullable=False),
        sa.UniqueConstraint(
            "person_id", "date", "role", name="uq_role_availability_person_date_role"
        ),
        sa.CheckConstraint(
            "role IN ('primary', 'substitute')", name="ck_role_availability_role"
        ),
    )
    op.create_index("ix_role_availability_date", "role_availability", ["date"])


def downgrade():
    raise RuntimeError(
        "Restore a private backup instead of deleting role-specific availability."
    )
