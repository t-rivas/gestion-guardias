from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Person(Base):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    blocked_weekdays: Mapped[str] = mapped_column(
        String(20), default="", nullable=False
    )

    @property
    def blocked_days(self) -> set[int]:
        return {
            int(value) for value in (self.blocked_weekdays or "").split(",") if value
        }
