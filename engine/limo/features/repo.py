import sqlite3
from pathlib import Path
from uuid import uuid4

from limo.common.errors import Conflict
from limo.features.models import Feature
from limo.store.db import connect


class FeatureRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def add(self, project_id: str, feature: Feature) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO features (id, project_id, name, phase, created_at) VALUES (?, ?, ?, ?, ?)",
                (uuid4().hex, project_id, feature.name, feature.phase, feature.created_at),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise Conflict("feature_exists", f"feature {feature.name} already exists") from e
        finally:
            conn.close()

    def get(self, project_id: str, name: str) -> Feature | None:
        conn = connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT name, phase, created_at FROM features WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else Feature(**dict(row))

    def set_phase(self, project_id: str, name: str, phase: str) -> None:
        conn = connect(self._db_path)
        try:
            conn.execute(
                "UPDATE features SET phase = ? WHERE project_id = ? AND name = ?", (phase, project_id, name)
            )
            conn.commit()
        finally:
            conn.close()

    def list(self, project_id: str) -> list[Feature]:
        conn = connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT name, phase, created_at FROM features WHERE project_id = ? ORDER BY created_at, name",
                (project_id,),
            ).fetchall()
        finally:
            conn.close()
        return [Feature(**dict(row)) for row in rows]
