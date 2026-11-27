import logging
from pathlib import Path

from limo.agents.repo import RunRepo
from limo.projects.repo import ProjectRepo
from limo.vcs.git import GitError, GitOps


class RecoveryService:
    def __init__(self, runs: RunRepo, projects: ProjectRepo, git: GitOps) -> None:
        self._runs = runs
        self._projects = projects
        self._git = git

    def recover(self) -> int:
        active = self._runs.active_runs()
        project_ids: set[str] = set()
        for run_id, project_id in active:
            self._runs.interrupt(run_id)
            project_ids.add(project_id)
        for project_id in project_ids:
            project = self._projects.get_by_id(project_id)
            if project is None or not Path(project.workspace).is_dir():
                continue
            try:
                self._git.reset_workspace(Path(project.workspace))
            except (GitError, OSError) as e:
                logging.getLogger(__name__).warning("workspace reset failed for %s: %s", project.name, e)
        return len(active)
