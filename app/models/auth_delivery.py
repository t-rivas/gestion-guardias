from sqlalchemy import Column, Integer, String

from app.db.base import Base


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key = Column(String(128), primary_key=True)
    count = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False, index=True)


class AuthDelivery(Base):
    __tablename__ = "auth_deliveries"
    event_id = Column(String(36), primary_key=True)
    fingerprint = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False)
    created_at = Column(Integer, nullable=False, index=True)
