"""SQLAlchemy ORM models for Vizhi AgentG local storage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class ConfigEntry(Base):
    """Key-value configuration store."""

    __tablename__ = "config"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)


class EngineLog(Base):
    """Persisted engine / runtime log lines."""

    __tablename__ = "engine_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class JobHistoryEntry(Base):
    """Completed / failed job records."""

    __tablename__ = "job_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(256), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    output = Column(Text, nullable=False, default="{}")
    error = Column(Text, nullable=False, default="")
    usage = Column(Text, nullable=False, default="{}")
    completed_at = Column(String(64), nullable=False, default="")


def build_engine(db_url: str):
    """Create a SQLAlchemy engine and ensure all tables exist."""
    engine = create_engine(db_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    return engine


def build_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
