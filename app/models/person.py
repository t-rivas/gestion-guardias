from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )