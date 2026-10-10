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


class RoleAvailability(Base):
    """Monthly role-specific exceptions layered over existing general availability."""

    __tablename__ = "role_availability"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "date", "role", name="uq_role_availability_person_date_role"
        ),
        CheckConstraint(
            "role IN ('primary', 'substitute')", name="ck_role_availability_role"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
