from dataclasses import dataclass
from typing import Literal, Protocol


class HostError(Exception):
    pass


@dataclass(frozen=True)
class HostProject:
    name: str
    git_url: str
    kind: str


@dataclass(frozen=True)
class MergeRequestRef:
    number: int
    url: str


@dataclass(frozen=True)
class IssueRef:
    number: int
    url: str


@dataclass(frozen=True)
class ReviewComment:
    id: str
    body: str


@dataclass(frozen=True)
class MrStatus:
    state: Literal["open", "merged", "closed"]
    approved: bool
    change_requests: list[ReviewComment]


class RepoHost(Protocol):
    def open_merge_request(
        self, project: HostProject, branch: str, base: str, title: str
    ) -> MergeRequestRef: ...

    def enable_auto_merge(self, project: HostProject, number: int) -> None: ...

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus: ...

    def create_issue(self, project: HostProject, title: str) -> IssueRef: ...

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None: ...
