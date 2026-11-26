import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from limo.common.errors import Conflict, ExternalError
from limo.executor.ports import Executor, ExecutorError
from limo.projects.models import Project, ProjectIn
from limo.projects.repo import ProjectRepo


class ProjectService:
    def __init__(self, repo: ProjectRepo, executor: Executor, workspaces: Path, timeout_s: float) -> None:
        self._repo = repo
        self._executor = executor
        self._workspaces = workspaces
        self._timeout_s = timeout_s

    def list(self) -> list[Project]:
        return self._repo.list_all()

    def add(self, data: ProjectIn) -> Project:
        if self._repo.get_by_name(data.name) is not None:
            raise Conflict("project_exists", f"project {data.name} already exists")
        self._workspaces.mkdir(parents=True, exist_ok=True)
        path = self._workspaces / data.name
        try:
            result = self._executor.run(
                ["git", "clone", "--", data.git_url, str(path)], self._workspaces, self._timeout_s
            )
        except ExecutorError as e:
            raise self._fail_clone(path) from e
        if result.code != 0:
            raise self._fail_clone(path)
        try:
            branch = self._executor.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path, self._timeout_s)
        except ExecutorError as e:
            raise self._fail_clone(path) from e
        if branch.code != 0 or not branch.stdout.strip():
            raise self._fail_clone(path)
        project = Project(
            id=str(uuid4()),
            name=data.name,
            git_url=data.git_url,
            host=data.host,
            status="ready",
            default_branch=branch.stdout.strip(),
            workspace=str(path),
            created_at=datetime.now(UTC).isoformat(),
        )
        self._repo.insert(project)
        return project

    def _fail_clone(self, path: Path) -> ExternalError:
        shutil.rmtree(path, ignore_errors=True)
        return ExternalError("clone_failed", "could not clone the repository")
