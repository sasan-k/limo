import sqlite3
from pathlib import Path

from limo.common.errors import Conflict
from limo.projects.models import Project
from limo.store.db import connect


class ProjectRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def insert(self, p: Project) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO projects"
                " (id, name, git_url, host, status, default_branch, workspace, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p.id, p.name, p.git_url, p.host, p.status, p.default_branch, p.workspace, p.created_at),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise Conflict("project_exists", f"project {p.name} already exists") from e
        finally:
            conn.close()

    def get_by_name(self, name: str) -> Project | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        finally:
            conn.close()
        return None if row is None else Project(**dict(row))

    def list_all(self) -> list[Project]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at, name").fetchall()
        finally:
            conn.close()
        return [Project(**dict(row)) for row in rows]
