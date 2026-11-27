from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from limo.inbox.models import Hold
from limo.store.db import connect


@dataclass(frozen=True)
class NewHold:
    project_id: str
    feature: str
    ticket: str
    kind: str
    reason: str


class HoldRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, hold: NewHold) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO holds (id, project_id, feature, ticket, kind, reason, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid4().hex,
                    hold.project_id,
                    hold.feature,
                    hold.ticket,
                    hold.kind,
                    hold.reason,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def open_list(self) -> list[Hold]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT h.id, p.name AS project, h.feature, h.ticket, h.kind, h.reason, h.created_at"
                " FROM holds h JOIN projects p ON p.id = h.project_id"
                " WHERE h.cleared_at IS NULL ORDER BY h.created_at, h.id"
            ).fetchall()
        finally:
            conn.close()
        return [Hold(**dict(row)) for row in rows]

    def get(self, hold_id: str) -> tuple[Hold, str | None] | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT h.id, p.name AS project, h.feature, h.ticket, h.kind, h.reason, h.created_at,"
                " h.cleared_at FROM holds h JOIN projects p ON p.id = h.project_id WHERE h.id = ?",
                (hold_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        data = dict(row)
        cleared_at = data.pop("cleared_at")
        return Hold(**data), cleared_at

    def clear(self, hold_id: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE holds SET cleared_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), hold_id),
            )
            conn.commit()
        finally:
            conn.close()

    def open_tickets(self, project_id: str, feature: str) -> set[str]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT ticket FROM holds"
                " WHERE project_id = ? AND feature = ? AND cleared_at IS NULL",
                (project_id, feature),
            ).fetchall()
        finally:
            conn.close()
        return {row[0] for row in rows}
