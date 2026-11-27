from dataclasses import dataclass
from pathlib import Path

from limo.store.db import connect


@dataclass(frozen=True)
class IssueRow:
    ticket: str
    number: int
    url: str
    status: str


class IssueRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def for_feature(self, project_id: str, feature: str) -> dict[str, IssueRow]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT ticket, number, url, status FROM issues WHERE project_id = ? AND feature = ?",
                (project_id, feature),
            ).fetchall()
        finally:
            conn.close()
        return {row["ticket"]: IssueRow(**dict(row)) for row in rows}

    def add(self, project_id: str, feature: str, row: IssueRow) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO issues (project_id, feature, ticket, number, url, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, feature, row.ticket, row.number, row.url, row.status),
            )
            conn.commit()
        finally:
            conn.close()

    def set_status(self, project_id: str, feature: str, ticket: str, status: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE issues SET status = ? WHERE project_id = ? AND feature = ? AND ticket = ?",
                (status, project_id, feature, ticket),
            )
            conn.commit()
        finally:
            conn.close()
