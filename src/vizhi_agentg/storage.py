"""SQLAlchemy-backed storage for Vizhi AgentG.

Uses SQLite via SQLAlchemy so the schema can be evolved with migrations
(e.g. Alembic) whenever the data model changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, desc, select

from .db_models import (
    ConfigEntry,
    EngineLog,
    JobHistoryEntry,
    build_engine,
    build_session_factory,
)
from .models import AgentConfig


class SQLiteStore:
    """SQLAlchemy-backed store that keeps config, logs and job history
    in a local SQLite database at ``~/.vizhi-agentg/vizhi_agentg.db``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".vizhi-agentg"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "vizhi_agentg.db"
        db_url = f"sqlite:///{self.db_path}"

        self._engine = build_engine(db_url)
        self._Session = build_session_factory(self._engine)

        # Auto-migrate old JSON config if present
        self._migrate_json_if_needed()

    # ── auto-migrate old JSON config ─────────────────────────────

    def _migrate_json_if_needed(self) -> None:
        old_config = self.root / "config.json"
        if not old_config.exists():
            return
        try:
            raw = json.loads(old_config.read_text(encoding="utf-8"))
            config = AgentConfig.model_validate(raw)
            # Only migrate if the DB has no config yet
            if self.load_config().agent_id == AgentConfig().agent_id:
                self.save_config(config)
        except Exception:
            pass  # skip migration on error; user will get defaults

    # ── config ───────────────────────────────────────────────────

    def load_config(self) -> AgentConfig:
        with self._Session() as session:
            row = session.execute(
                select(ConfigEntry).where(ConfigEntry.key == "agent_config")
            ).scalar_one_or_none()
        if row is None:
            return AgentConfig()
        return AgentConfig.model_validate(json.loads(row.value))

    def save_config(self, config: AgentConfig) -> None:
        blob = json.dumps(config.model_dump(mode="json"))
        with self._Session() as session:
            existing = session.execute(
                select(ConfigEntry).where(ConfigEntry.key == "agent_config")
            ).scalar_one_or_none()
            if existing:
                existing.value = blob
            else:
                session.add(ConfigEntry(key="agent_config", value=blob))
            session.commit()

    # ── engine logs ──────────────────────────────────────────────

    def add_log(self, message: str) -> None:
        ts = datetime.now(timezone.utc)
        with self._Session() as session:
            session.add(EngineLog(message=message, timestamp=ts))
            session.commit()

            # keep only last 500 rows
            count = session.query(EngineLog).count()
            if count > 500:
                cutoff_id = session.execute(
                    select(EngineLog.id).order_by(desc(EngineLog.id)).offset(500).limit(1)
                ).scalar()
                if cutoff_id is not None:
                    session.execute(
                        delete(EngineLog).where(EngineLog.id <= cutoff_id)
                    )
                    session.commit()

    def get_logs(self, limit: int = 50) -> list[dict[str, str]]:
        with self._Session() as session:
            rows = session.execute(
                select(EngineLog).order_by(desc(EngineLog.id)).limit(limit)
            ).scalars().all()
        return [
            {
                "message": r.message,
                "timestamp": (
                    r.timestamp.isoformat(timespec="seconds")
                    if isinstance(r.timestamp, datetime)
                    else str(r.timestamp)
                ),
            }
            for r in rows
        ]

    # ── job history ──────────────────────────────────────────────

    def add_job_result(self, result: dict[str, Any]) -> None:
        with self._Session() as session:
            session.add(
                JobHistoryEntry(
                    job_id=result.get("job_id", ""),
                    status=result.get("status", ""),
                    output=json.dumps(result.get("output", {})),
                    error=result.get("error", ""),
                    usage=json.dumps(result.get("usage", {})),
                    completed_at=result.get("completed_at", ""),
                )
            )
            session.commit()

            # keep only last 200 rows
            count = session.query(JobHistoryEntry).count()
            if count > 200:
                cutoff_id = session.execute(
                    select(JobHistoryEntry.id)
                    .order_by(desc(JobHistoryEntry.id))
                    .offset(200)
                    .limit(1)
                ).scalar()
                if cutoff_id is not None:
                    session.execute(
                        delete(JobHistoryEntry).where(JobHistoryEntry.id <= cutoff_id)
                    )
                    session.commit()

    def get_job_history(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._Session() as session:
            rows = session.execute(
                select(JobHistoryEntry)
                .order_by(desc(JobHistoryEntry.id))
                .limit(limit)
            ).scalars().all()
        return [
            {
                "job_id": r.job_id,
                "status": r.status,
                "output": json.loads(r.output) if r.output else {},
                "error": r.error,
                "usage": json.loads(r.usage) if r.usage else {},
                "completed_at": r.completed_at,
            }
            for r in rows
        ]


# Backward-compatible alias so old imports still work
FileStore = SQLiteStore
