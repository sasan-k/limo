from dataclasses import dataclass
from pathlib import Path

from limo.agents.models import RunStatus
from limo.store.db import connect

LATEST_RUNS_SQL = """
SELECT r.agent, r.id AS run_id, p.name AS project, r.feature, r.ticket, r.status, r.attempt,
  r.created_at, r.finished_at,
  (SELECT COALESCE(SUM(u.input_tokens + u.output_tokens + u.cache_read_tokens + u.cache_write_tokens), 0)
     FROM usage u WHERE u.run_id = r.id) AS tokens,
  (SELECT COALESCE(SUM(u.cost_micros), 0) FROM usage u
     WHERE u.project_id = r.project_id AND u.feature = r.feature AND u.ticket IS r.ticket
       AND u.agent = r.agent) AS cost_micros,
  EXISTS (SELECT 1 FROM incidents i
     WHERE i.project_id = r.project_id AND i.feature = r.feature AND i.ticket = r.ticket
       AND (i.status = 'open' OR (i.status = 'needs_human' AND i.reply IS NULL))) AS has_incident
FROM (SELECT runs.*, ROW_NUMBER() OVER (PARTITION BY agent ORDER BY created_at DESC, rowid DESC) AS rn
      FROM runs) r
JOIN projects p ON p.id = r.project_id
WHERE r.rn = 1
"""


@dataclass(frozen=True)
class CardRow:
    agent: str
    run_id: str
    project: str
    feature: str
    ticket: str | None
    status: RunStatus
    attempt: int
    created_at: str
    finished_at: str | None
    tokens: int
    cost_micros: int
    has_incident: bool


class CardRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def latest_runs(self) -> list[CardRow]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(LATEST_RUNS_SQL).fetchall()
        finally:
            conn.close()
        return [CardRow(**{**dict(row), "has_incident": bool(row["has_incident"])}) for row in rows]
