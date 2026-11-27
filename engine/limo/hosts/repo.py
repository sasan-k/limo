import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from limo.hosts.ports import MergeRequestRef
from limo.store.db import connect


@dataclass(frozen=True)
class NewMr:
    project_id: str
    feature: str
    ticket: str
    branch: str


@dataclass(frozen=True)
class MrRecord:
    id: int
    project_id: str
    feature: str
    ticket: str
    number: int
    url: str
    branch: str
    state: str
    last_review_id: str
    needs_push: bool


def _record(row: sqlite3.Row) -> MrRecord:
    data = dict(row)
    data["needs_push"] = bool(data["needs_push"])
    return MrRecord(**data)


class MergeRequestRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, new: NewMr, ref: MergeRequestRef) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO merge_requests"
                " (project_id, feature, ticket, number, url, branch, state, last_review_id, needs_push,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', '', 0, ?)",
                (
                    new.project_id,
                    new.feature,
                    new.ticket,
                    ref.number,
                    ref.url,
                    new.branch,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def open_for(self, project_id: str, feature: str) -> list[MrRecord]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT id, project_id, feature, ticket, number, url, branch, state,"
                " last_review_id, needs_push FROM merge_requests"
                " WHERE project_id = ? AND feature = ?"
                " AND state = 'open' ORDER BY id",
                (project_id, feature),
            ).fetchall()
        finally:
            conn.close()
        return [_record(row) for row in rows]

    def open_for_ticket(self, project_id: str, feature: str, ticket: str) -> MrRecord | None:
        for record in self.open_for(project_id, feature):
            if record.ticket == ticket:
                return record
        return None

    def set_state(self, mr_id: int, state: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute("UPDATE merge_requests SET state = ? WHERE id = ?", (state, mr_id))
            conn.commit()
        finally:
            conn.close()

    def set_review(self, mr_id: int, last_review_id: str, needs_push: bool) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE merge_requests SET last_review_id = ?, needs_push = ? WHERE id = ?",
                (last_review_id, int(needs_push), mr_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_needs_push(self, mr_id: int, value: bool) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute("UPDATE merge_requests SET needs_push = ? WHERE id = ?", (int(value), mr_id))
            conn.commit()
        finally:
            conn.close()
