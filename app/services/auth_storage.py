import hashlib
import hmac
import time

from sqlalchemy import case, delete, or_

from app.models.auth_delivery import AuthRateLimit


def insert_for(db, model):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif db.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(
            "Auth shared storage requires PostgreSQL or isolated SQLite tests."
        )
    return insert(model)


def take_rate_limit(db, scope, subject, secret, *, limit=1, seconds=60, now=None):
    now = int(time.time()) if now is None else now
    digest = hmac.new(secret.encode(), subject.encode(), hashlib.sha256).hexdigest()
    key = f"{scope}:{digest}"
    db.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at <= now))
    statement = insert_for(db, AuthRateLimit).values(
        key=key, count=1, expires_at=now + seconds
    )
    expired = AuthRateLimit.expires_at <= now
    statement = statement.on_conflict_do_update(
        index_elements=[AuthRateLimit.key],
        set_={
            "count": case((expired, 1), else_=AuthRateLimit.count + 1),
            "expires_at": case(
                (expired, now + seconds), else_=AuthRateLimit.expires_at
            ),
        },
        where=or_(expired, AuthRateLimit.count < limit),
    ).returning(AuthRateLimit.count)
    allowed = db.execute(statement).scalar_one_or_none() is not None
    db.commit()
    return allowed
