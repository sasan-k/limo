from dataclasses import dataclass
from pathlib import Path

from limo.store.db import connect


@dataclass(frozen=True)
class BudgetKey:
    project_id: str
    feature: str
    ticket: str


class BudgetRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def defaults(self) -> tuple[int, int] | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT ticket_micros, agent_micros FROM budget_defaults WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else (row[0], row[1])

    def set_defaults(self, ticket_micros: int, agent_micros: int) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO budget_defaults (id, ticket_micros, agent_micros) VALUES (1, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET ticket_micros = excluded.ticket_micros,"
                " agent_micros = excluded.agent_micros",
                (ticket_micros, agent_micros),
            )
            conn.commit()
        finally:
            conn.close()

    def overrides(self, project_id: str, feature: str, ticket: str) -> dict[str, int]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT agent, budget_micros FROM ticket_budgets"
                " WHERE project_id = ? AND feature = ? AND ticket = ?",
                (project_id, feature, ticket),
            ).fetchall()
        finally:
            conn.close()
        return {row[0]: row[1] for row in rows}

    def set_override(self, key: BudgetKey, agent: str, micros: int) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO ticket_budgets (project_id, feature, ticket, agent, budget_micros)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(project_id, feature, ticket, agent)"
                " DO UPDATE SET budget_micros = excluded.budget_micros",
                (key.project_id, key.feature, key.ticket, agent, micros),
            )
            conn.commit()
        finally:
            conn.close()
