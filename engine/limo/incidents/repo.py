import builtins
from datetime import UTC, datetime
from pathlib import Path

from limo.incidents.models import IncidentRow
from limo.store.db import connect


class IncidentRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, project_id: str, feature: str, row: IncidentRow) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO incidents"
                " (id, project_id, feature, ticket, k, trigger, status, run_id, resolver_run_id, action,"
                " created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row.id,
                    project_id,
                    feature,
                    row.ticket,
                    row.k,
                    row.trigger,
                    row.status,
                    row.run_id,
                    row.resolver_run_id,
                    row.action,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list(self, project_id: str, feature: str) -> list[IncidentRow]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT id, ticket, k, trigger, status, run_id, resolver_run_id, action FROM incidents"
                " WHERE project_id = ? AND feature = ? ORDER BY rowid",
                (project_id, feature),
            ).fetchall()
        finally:
            conn.close()
        return [IncidentRow(**dict(row)) for row in rows]

    def open_for(self, project_id: str, feature: str) -> builtins.list[IncidentRow]:
        return [row for row in self.list(project_id, feature) if row.status == "open"]

    def blocking_tickets(self, project_id: str, feature: str) -> set[str]:
        return {row.ticket for row in self.list(project_id, feature) if row.status in ("open", "needs_human")}

    def count_for(self, project_id: str, feature: str, ticket: str) -> int:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE project_id = ? AND feature = ? AND ticket = ?",
                (project_id, feature, ticket),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0])

    def exists_for_run(self, project_id: str, ticket: str, trigger: str, run_id: str | None) -> bool:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM incidents WHERE project_id = ? AND ticket = ? AND trigger = ?"
                " AND run_id IS ? LIMIT 1",
                (project_id, ticket, trigger, run_id),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def set_resolver_run(self, incident_id: str, run_id: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute("UPDATE incidents SET resolver_run_id = ? WHERE id = ?", (run_id, incident_id))
            conn.commit()
        finally:
            conn.close()

    def close(self, incident_id: str, status: str, action: str | None) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE incidents SET status = ?, action = ? WHERE id = ?", (status, action, incident_id)
            )
            conn.commit()
        finally:
            conn.close()
