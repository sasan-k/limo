from datetime import UTC, datetime
from pathlib import Path

from limo.common.constants import AGENT_NAMES
from limo.common.errors import Conflict, NotFound
from limo.events.bus import EventBus
from limo.prompts.models import PromptFile, PromptSaveIn, PromptVersion
from limo.prompts.repo import PromptSaveRepo
from limo.vcs.git import FileVersion, GitError, GitOps

HISTORY_LIMIT = 50


def _utc(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(UTC).isoformat()


class PromptService:
    """Agent prompt and reference files in skills/; every change is a git commit (REQ-42, REQ-43)."""

    def __init__(self, skills_dir: Path, git: GitOps, saves: PromptSaveRepo, events: EventBus) -> None:
        self._skills_dir = skills_dir
        self._git = git
        self._saves = saves
        self._events = events

    def files(self, agent: str) -> list[str]:
        root = self._agent_dir(agent)
        templates = root / "templates"
        if not templates.is_dir():
            return ["SKILL.md"]
        refs = sorted(p.relative_to(root).as_posix() for p in templates.rglob("*") if p.is_file())
        return ["SKILL.md", *refs]

    def read(self, agent: str, path: str) -> PromptFile:
        root, file = self._resolve(agent, path)
        return PromptFile(agent=agent, path=path, content=file.read_text(), version=self._head(root, path))

    def history(self, agent: str, path: str) -> list[PromptVersion]:
        root, _ = self._resolve(agent, path)
        return [
            PromptVersion(version=v.version, saved_at=_utc(v.saved_at), message=v.message)
            for v in self._versions(root, path, HISTORY_LIMIT)
        ]

    def save(self, agent: str, path: str, data: PromptSaveIn) -> PromptFile:
        root, file = self._resolve(agent, path)
        head = self._head(root, path)
        if data.base_version is not None and data.base_version != head:
            raise Conflict("version_conflict", f"{path} changed since {data.base_version[:7]}")
        if file.read_text() != data.content:
            file.write_text(data.content)
            self._commit(agent, root, path, (f"prompt: {agent} {path}", "save"))
        return self.read(agent, path)

    def rollback(self, agent: str, path: str, version: str) -> PromptFile:
        root, file = self._resolve(agent, path)
        known = [v.version for v in self._versions(root, path, HISTORY_LIMIT)]
        if version not in known:
            raise NotFound("version_not_found", f"version {version[:7]} is not in the history of {path}")
        before = file.read_text()
        if version != known[0]:
            try:
                self._git.restore_file(root, version, path)
            except GitError as e:
                raise Conflict("git_failed", "prompt rollback failed") from e
        if file.read_text() != before:
            self._commit(agent, root, path, (f"prompt: rollback {agent} {path} to {version[:7]}", "rollback"))
        return self.read(agent, path)

    def _commit(self, agent: str, root: Path, path: str, what: tuple[str, str]) -> None:
        message, action = what
        try:
            self._git.commit_file(root, path, message)
        except GitError as e:
            raise Conflict("git_failed", "prompt commit failed") from e
        version = self._head(root, path) or ""
        self._saves.add(agent, path, version, action)
        self._events.publish("prompt.saved", None, {"agent": agent, "path": path, "version": version})

    def _versions(self, root: Path, path: str, limit: int) -> list[FileVersion]:
        try:
            return self._git.file_versions(root, path, limit)
        except GitError as e:
            raise Conflict(
                "git_failed", "prompt history unavailable: skills are not in a git repository"
            ) from e

    def _head(self, root: Path, path: str) -> str | None:
        versions = self._versions(root, path, 1)
        return versions[0].version if versions else None

    def _agent_dir(self, agent: str) -> Path:
        if agent not in AGENT_NAMES:
            raise NotFound("agent_not_found", f"agent {agent} not found")
        return self._skills_dir / agent

    def _resolve(self, agent: str, path: str) -> tuple[Path, Path]:
        root = self._agent_dir(agent)
        file = root / path
        inside = file.resolve().is_relative_to(root.resolve())
        if file.is_symlink() or not file.is_file() or not inside:
            raise NotFound("file_not_found", f"{path} not found for agent {agent}")
        return root, file
