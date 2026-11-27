from limo.hosts.ports import (
    HostError,
    HostProject,
    IssueComment,
    IssueRef,
    MergeRequestRef,
    MrStatus,
    RepoHost,
)


class RoutedHost:
    def __init__(self, github: RepoHost, gitlab: RepoHost) -> None:
        self._hosts: dict[str, RepoHost] = {"github": github, "gitlab": gitlab}

    def _pick(self, project: HostProject) -> RepoHost:
        host = self._hosts.get(project.kind)
        if host is None:
            raise HostError("unknown repo host")
        return host

    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        return self._pick(project).open_merge_request(project, branch, base, title)

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        self._pick(project).enable_auto_merge(project, number)

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        return self._pick(project).merge_request_status(project, number)

    def create_issue(self, project: HostProject, title: str) -> IssueRef:
        return self._pick(project).create_issue(project, title)

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None:
        self._pick(project).set_issue_status(project, number, status)

    def set_issue_title(self, project: HostProject, number: int, title: str) -> None:
        self._pick(project).set_issue_title(project, number, title)

    def add_issue_label(self, project: HostProject, number: int, label: str) -> None:
        self._pick(project).add_issue_label(project, number, label)

    def comment_issue(self, project: HostProject, number: int, body: str) -> None:
        self._pick(project).comment_issue(project, number, body)

    def issue_comments(self, project: HostProject, number: int) -> list[IssueComment]:
        return self._pick(project).issue_comments(project, number)
