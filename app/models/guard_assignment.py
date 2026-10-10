from datetime import date
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class GuardAssignment(Base):
    __tablename__ = "guard_assignments"
    __table_args__ = (
        UniqueConstraint("date", "slot", name="uq_guard_assignments_date_slot"),
        UniqueConstraint("date", "person_id", name="uq_guard_assignments_date_person"),
        CheckConstraint(
            "(slot BETWEEN 1 AND 3 AND role = 'primary') OR (slot = 4 AND role = 'substitute')",
            name="ck_assignment_role_slot",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="primary")
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
