from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GuardAssignment(Base):
    __tablename__ = "guard_assignments"
    __table_args__ = (
        UniqueConstraint("date", name="uq_guard_assignments_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id"),
        nullable=False,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
