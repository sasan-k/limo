from datetime import UTC, datetime
from pathlib import Path

from limo.store.db import connect


class PromptSaveRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, agent: str, path: str, version: str, action: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO prompt_saves (agent, path, version, action, created_at) VALUES (?, ?, ?, ?, ?)",
                (agent, path, version, action, datetime.now(UTC).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
