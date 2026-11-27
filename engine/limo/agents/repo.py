from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from limo.agents.models import Run, ToolCall
from limo.store.db import connect


class RunRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def insert(self, run: Run, project_id: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO runs"
                " (id, project_id, agent, feature, ticket, status, model, output, error,"
                " created_at, finished_at, args, ticket_status)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.id,
                    project_id,
                    run.agent,
                    run.feature,
                    run.ticket,
                    run.status,
                    run.model,
                    run.output,
                    run.error,
                    run.created_at,
                    run.finished_at,
                    run.args,
                    run.ticket_status,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, run_id: str) -> Run | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT r.id, p.name AS project, r.agent, r.feature, r.ticket, r.status, r.model,"
                " r.output, r.error, r.created_at, r.finished_at, r.args, r.ticket_status"
                " FROM runs r JOIN projects p ON p.id = r.project_id WHERE r.id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else Run(**dict(row))

    def latest(self, project_id: str, feature: str, agent: str, args: str | None) -> Run | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT r.id, p.name AS project, r.agent, r.feature, r.ticket, r.status, r.model,"
                " r.output, r.error, r.created_at, r.finished_at, r.args, r.ticket_status"
                " FROM runs r JOIN projects p ON p.id = r.project_id"
                " WHERE r.project_id = ? AND r.feature = ? AND r.agent = ? AND r.args IS ?"
                " ORDER BY r.created_at DESC LIMIT 1",
                (project_id, feature, agent, args),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else Run(**dict(row))

    def latest_for_ticket(self, project_id: str, feature: str, ticket: str) -> Run | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT r.id, p.name AS project, r.agent, r.feature, r.ticket, r.status, r.model,"
                " r.output, r.error, r.created_at, r.finished_at, r.args, r.ticket_status"
                " FROM runs r JOIN projects p ON p.id = r.project_id"
                " WHERE r.project_id = ? AND r.feature = ? AND r.ticket = ? AND r.agent != 'resolver'"
                " ORDER BY r.created_at DESC LIMIT 1",
                (project_id, feature, ticket),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else Run(**dict(row))

    def active_older_than(self, project_id: str, cutoff_iso: str) -> list[str]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT id FROM runs WHERE project_id = ? AND status IN ('queued', 'running')"
                " AND created_at < ?",
                (project_id, cutoff_iso),
            ).fetchall()
        finally:
            conn.close()
        return [str(row["id"]) for row in rows]

    def set_status(self, run_id: str, status: Literal["queued", "running", "succeeded", "failed"]) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))
            conn.commit()
        finally:
            conn.close()

    def finish(
        self,
        run_id: str,
        status: Literal["queued", "running", "succeeded", "failed"],
        output: str | None,
        error: str | None,
    ) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE runs SET status = ?, output = ?, error = ?, finished_at = ?"
                " WHERE id = ? AND status IN ('queued', 'running')",
                (status, output, error, datetime.now(UTC).isoformat(), run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def add_tool_call(self, run_id: str, call: ToolCall) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO tool_calls (run_id, seq, name, target, status, summary, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    call.seq,
                    call.name,
                    call.target,
                    call.status,
                    call.summary,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def tool_calls(self, run_id: str) -> list[ToolCall]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT seq, name, target, status, summary FROM tool_calls WHERE run_id = ? ORDER BY seq",
                (run_id,),
            ).fetchall()
        finally:
            conn.close()
        return [ToolCall(**dict(row)) for row in rows]

    def active_count(self) -> int:
        conn = connect(self._db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM runs WHERE status IN ('queued', 'running')").fetchone()
        finally:
            conn.close()
        return int(row[0])
