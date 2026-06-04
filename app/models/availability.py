from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Availability(Base):
    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id"),
        nullable=False,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )