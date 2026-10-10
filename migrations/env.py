from alembic import context
from sqlalchemy import create_engine
from app.db.base import Base
import app.models
from app.auth_config import database_url

config = context.config


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Run these migrations against a database connection.")
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = create_engine(database_url(migration=True))
    with engine.connect() as connection:
        run(connection)
