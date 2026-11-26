from datetime import UTC, datetime
from pathlib import Path

from limo.store.db import connect


class AgentSettingsRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get(self, agent: str) -> str | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute("SELECT model FROM agent_settings WHERE agent = ?", (agent,)).fetchone()
        finally:
            conn.close()
        return None if row is None else row["model"]

    def all(self) -> dict[str, str]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute("SELECT agent, model FROM agent_settings").fetchall()
        finally:
            conn.close()
        return {row["agent"]: row["model"] for row in rows}

    def set(self, agent: str, model: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO agent_settings (agent, model, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(agent) DO UPDATE SET model = excluded.model, updated_at = excluded.updated_at",
                (agent, model, datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
