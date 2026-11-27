import builtins
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from limo.incidents.models import IncidentRow
from limo.store.db import connect


@dataclass(frozen=True)
class Escalation:
    row: IncidentRow
    project: str
    feature: str
    created_at: str


class IncidentRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, project_id: str, feature: str, row: IncidentRow) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO incidents"
                " (id, project_id, feature, ticket, k, trigger, status, run_id, resolver_run_id, action,"
                " human_input, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    1 if row.human_input else 0,
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
                "SELECT id, ticket, k, trigger, status, run_id, resolver_run_id, action, note_pending,"
                " ask, reply, human_input, last_comment_id"
                " FROM incidents WHERE project_id = ? AND feature = ? ORDER BY rowid",
                (project_id, feature),
            ).fetchall()
        finally:
            conn.close()
        return [_row(row) for row in rows]

    def get(self, incident_id: str) -> IncidentRow | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT id, ticket, k, trigger, status, run_id, resolver_run_id, action, note_pending,"
                " ask, reply, human_input, last_comment_id FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else _row(row)

    def open_for(self, project_id: str, feature: str) -> builtins.list[IncidentRow]:
        return [row for row in self.list(project_id, feature) if row.status == "open"]

    def awaiting_reply(self, project_id: str, feature: str) -> builtins.list[IncidentRow]:
        return [
            row for row in self.list(project_id, feature) if row.status == "needs_human" and row.reply is None
        ]

    def replied(self, project_id: str, feature: str) -> builtins.list[IncidentRow]:
        return [
            row
            for row in self.list(project_id, feature)
            if row.status == "needs_human" and row.reply is not None
        ]

    def escalations(self) -> builtins.list[Escalation]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT i.id, i.ticket, i.k, i.trigger, i.status, i.run_id, i.resolver_run_id, i.action,"
                " i.note_pending, i.ask, i.reply, i.human_input, i.last_comment_id,"
                " p.name AS project, i.feature, i.created_at"
                " FROM incidents i JOIN projects p ON p.id = i.project_id"
                " WHERE i.status = 'needs_human' AND i.reply IS NULL ORDER BY i.rowid"
            ).fetchall()
        finally:
            conn.close()
        result = []
        for r in rows:
            data = dict(r)
            project, feature, created_at = data.pop("project"), data.pop("feature"), data.pop("created_at")
            result.append(Escalation(_row(data), str(project), str(feature), str(created_at)))
        return result

    def blocking_tickets(self, project_id: str, feature: str) -> set[str]:
        return {
            row.ticket
            for row in self.list(project_id, feature)
            if row.status == "open" or (row.status == "needs_human" and row.reply is None)
        }

    def resolver_count(self, project_id: str, feature: str, ticket: str) -> int:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE project_id = ? AND feature = ? AND ticket = ?"
                " AND resolver_run_id IS NOT NULL AND human_input = 0",
                (project_id, feature, ticket),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0])

    def set_ask(self, incident_id: str, ask: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute("UPDATE incidents SET ask = ? WHERE id = ?", (ask, incident_id))
            conn.commit()
        finally:
            conn.close()

    def set_reply(self, incident_id: str, reply: str, comment_id: str | None) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE incidents SET reply = ?, last_comment_id = ? WHERE id = ?",
                (reply, comment_id, incident_id),
            )
            conn.commit()
        finally:
            conn.close()

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
        if run_id is None:
            return False
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

    def actions_for(self, project_id: str, feature: str, ticket: str) -> builtins.list[str]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT action FROM incidents WHERE project_id = ? AND feature = ? AND ticket = ?"
                " AND action IS NOT NULL ORDER BY rowid",
                (project_id, feature, ticket),
            ).fetchall()
        finally:
            conn.close()
        return [str(row["action"]) for row in rows]

    def set_note_pending(self, incident_id: str, value: bool) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE incidents SET note_pending = ? WHERE id = ?", (1 if value else 0, incident_id)
            )
            conn.commit()
        finally:
            conn.close()

    def pending_note(self, project_id: str, feature: str, ticket: str) -> tuple[str, str] | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT id, action FROM incidents WHERE project_id = ? AND feature = ? AND ticket = ?"
                " AND note_pending = 1 ORDER BY rowid DESC LIMIT 1",
                (project_id, feature, ticket),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return str(row["id"]), str(json.loads(row["action"])["fix"])


def _row(row: Any) -> IncidentRow:
    data = dict(row)
    return IncidentRow(
        **{
            **data,
            "note_pending": bool(data["note_pending"]),
            "human_input": bool(data["human_input"]),
        }
    )
