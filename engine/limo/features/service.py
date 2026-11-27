from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from limo.common.errors import Conflict, NotFound
from limo.features.models import Feature, FeatureIn
from limo.features.repo import FeatureRepo
from limo.projects.models import Project
from limo.projects.repo import ProjectRepo


class FeatureService:
    def __init__(self, features: FeatureRepo, projects: ProjectRepo) -> None:
        self._features = features
        self._projects = projects

    def create(self, project_name: str, data: FeatureIn) -> Feature:
        project = self._project(project_name)
        workspace = Path(project.workspace)
        if self._features.get(project.id, data.name) is not None or (workspace / "work" / data.name).exists():
            raise Conflict("feature_exists", f"feature {data.name} already exists")
        requirements = workspace / "work" / data.name / "requirements" / f"{data.name}.md"
        requirements.parent.mkdir(parents=True, exist_ok=True)
        requirements.write_text(data.requirements)
        phase: Literal["architecture", "spec"] = (
            "spec" if (workspace / "context").is_dir() else "architecture"
        )
        feature = Feature(name=data.name, phase=phase, created_at=datetime.now(UTC).isoformat())
        self._features.add(project.id, feature)
        return feature

    def list(self, project_name: str) -> list[Feature]:
        project = self._project(project_name)
        return self._features.list(project.id)

    def _project(self, project_name: str) -> Project:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        return project
