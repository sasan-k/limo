from dataclasses import dataclass
from pathlib import Path

from limo.executor.ports import CommandResult, Executor, ExecutorError

IDENTITY = ("-c", "user.name=Limo", "-c", "user.email=limo@localhost")


class GitError(Exception):
    pass


@dataclass(frozen=True)
class FileVersion:
    version: str
    saved_at: str
    message: str


class GitOps:
    def __init__(self, executor: Executor, timeout_s: float) -> None:
        self._executor = executor
        self._timeout_s = timeout_s

    def _git(self, workspace: Path, *args: str) -> CommandResult:
        try:
            return self._executor.run(["git", *args], workspace, self._timeout_s)
        except ExecutorError as e:
            raise GitError(str(e)) from e

    def _has_ref(self, workspace: Path, ref: str) -> bool:
        return self._git(workspace, "rev-parse", "--verify", "--quiet", ref).code == 0

    def start_ticket(self, workspace: Path, branch: str, base: str) -> None:
        fetched = self._git(workspace, "fetch", "origin")
        if fetched.code != 0:
            raise GitError(fetched.stderr)
        if self._has_ref(workspace, f"refs/heads/{branch}"):
            checkout = self._git(workspace, "checkout", branch)
        elif self._has_ref(workspace, f"refs/remotes/origin/{branch}"):
            checkout = self._git(workspace, "checkout", "-B", branch, f"origin/{branch}")
        else:
            checkout = self._git(workspace, "checkout", "-B", branch, f"origin/{base}")
        if checkout.code != 0:
            raise GitError(checkout.stderr)

    def reset_workspace(self, workspace: Path) -> None:
        reset = self._git(workspace, "reset", "--hard", "HEAD")
        if reset.code != 0:
            raise GitError(reset.stderr)
        cleaned = self._git(workspace, "clean", "-fd", "-e", "work")
        if cleaned.code != 0:
            raise GitError(cleaned.stderr)

    def commit_and_push(self, workspace: Path, branch: str, message: str) -> None:
        added = self._git(workspace, "add", "-A")
        if added.code != 0:
            raise GitError(added.stderr)
        self._git(workspace, "reset", "-q", "--", "work")
        committed = self._git(workspace, *IDENTITY, "commit", "-m", message)
        if committed.code != 0 and "nothing to commit" not in committed.stdout:
            raise GitError(committed.stderr or committed.stdout)
        pushed = self._git(workspace, "push", "-u", "origin", branch)
        if pushed.code != 0:
            raise GitError(pushed.stderr)

    def file_versions(self, cwd: Path, path: str, limit: int) -> list[FileVersion]:
        result = self._git(cwd, "log", f"-n{limit}", "--format=%H%x09%cI%x09%s", "--", path)
        if result.code != 0:
            raise GitError(result.stderr)
        versions: list[FileVersion] = []
        for line in result.stdout.splitlines():
            sha, _, rest = line.partition("\t")
            saved_at, _, message = rest.partition("\t")
            versions.append(FileVersion(sha, saved_at, message))
        return versions

    def commit_file(self, cwd: Path, path: str, message: str) -> None:
        committed = self._git(cwd, *IDENTITY, "commit", "-m", message, "--", path)
        if committed.code != 0:
            raise GitError(committed.stderr or committed.stdout)

    def restore_file(self, cwd: Path, version: str, path: str) -> None:
        restored = self._git(cwd, "checkout", version, "--", path)
        if restored.code != 0:
            raise GitError(restored.stderr)
