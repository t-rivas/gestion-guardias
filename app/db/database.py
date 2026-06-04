import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://guardias:guardias@localhost:5433/guardias",
)
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"

engine = create_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
