import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from limo.hosts.ports import (
    HostError,
    HostProject,
    IssueComment,
    IssueRef,
    MergeRequestRef,
    MrStatus,
    ReviewComment,
)


@dataclass
class FakeIssue:
    title: str
    labels: list[str]
    comments: list[IssueComment] = field(default_factory=list)


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
        self.issues: dict[int, FakeIssue] = {}
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

    def create_issue(self, project: HostProject, title: str) -> IssueRef:
        self._check("create_issue")
        number = len(self.issues) + 1
        self.issues[number] = FakeIssue(title=title, labels=[])
        self.calls.append(("create_issue", title))
        return IssueRef(number=number, url=f"https://host.example/issues/{number}")

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None:
        self._check("set_issue_status")
        issue = self.issues[number]
        issue.labels = [label for label in issue.labels if not label.startswith("limo:")]
        issue.labels.append(f"limo:{status}")
        self.calls.append(("set_issue_status", number))

    def set_issue_title(self, project: HostProject, number: int, title: str) -> None:
        self._check("set_issue_title")
        self.issues[number].title = title
        self.calls.append(("set_issue_title", number))

    def add_issue_label(self, project: HostProject, number: int, label: str) -> None:
        self._check("add_issue_label")
        issue = self.issues[number]
        if label not in issue.labels:
            issue.labels.append(label)
        self.calls.append(("add_issue_label", number))

    def comment_issue(self, project: HostProject, number: int, body: str) -> None:
        self._check("comment_issue")
        issue = self.issues[number]
        issue.comments.append(IssueComment(f"k{len(issue.comments) + 1}", body, True))
        self.calls.append(("comment_issue", number))

    def issue_comments(self, project: HostProject, number: int) -> list[IssueComment]:
        self._check("issue_comments")
        self.calls.append(("issue_comments", number))
        return list(self.issues[number].comments)

    def reply(self, number: int, body: str) -> None:
        issue = self.issues[number]
        issue.comments.append(IssueComment(f"k{len(issue.comments) + 1}", body, False))

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
