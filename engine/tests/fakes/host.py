import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from limo.hosts.ports import HostError, HostProject, MergeRequestRef, MrStatus, ReviewComment


@dataclass
class FakeMr:
    branch: str
    base: str
    title: str
    git_url: str
    state: str = "open"
    approved: bool = False
    comments: list[ReviewComment] = field(default_factory=list)


class FakeHost:
    """In-memory RepoHost. Test controls (approve, request_changes, merge) are not part of the port."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int | str]] = []
        self.mrs: dict[int, FakeMr] = {}
        self.fail_next: set[str] = set()

    def _check(self, name: str) -> None:
        if name in self.fail_next:
            self.fail_next.discard(name)
            raise HostError("fake failure")

    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        self._check("open_merge_request")
        number = len(self.mrs) + 1
        self.mrs[number] = FakeMr(branch=branch, base=base, title=title, git_url=project.git_url)
        self.calls.append(("open_merge_request", branch))
        return MergeRequestRef(number=number, url=f"https://host.example/mr/{number}")

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        self._check("enable_auto_merge")
        self.calls.append(("enable_auto_merge", number))

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        self._check("merge_request_status")
        self.calls.append(("merge_request_status", number))
        mr = self.mrs[number]
        return MrStatus(state=mr.state, approved=mr.approved, change_requests=list(mr.comments))

    def approve(self, number: int) -> None:
        self.mrs[number].approved = True

    def request_changes(self, number: int, body: str) -> None:
        mr = self.mrs[number]
        mr.comments.append(ReviewComment(id=f"c{len(mr.comments) + 1}", body=body))

    def merge(self, number: int) -> None:
        mr = self.mrs[number]
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "clone"
            subprocess.run(["git", "clone", mr.git_url, str(clone)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(clone), "checkout", mr.base], check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone),
                    "-c",
                    "user.name=t",
                    "-c",
                    "user.email=t@t",
                    "merge",
                    "--no-ff",
                    f"origin/{mr.branch}",
                    "-m",
                    "merge",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone), "push", "origin", mr.base], check=True, capture_output=True
            )
        mr.state = "merged"
