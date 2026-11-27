from limo.hosts.ports import HostError, HostProject, IssueComment, IssueRef, MergeRequestRef, MrStatus


class UnconfiguredHost:
    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        raise HostError("repo host adapter not configured")

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        raise HostError("repo host adapter not configured")

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        raise HostError("repo host adapter not configured")

    def create_issue(self, project: HostProject, title: str) -> IssueRef:
        raise HostError("repo host adapter not configured")

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None:
        raise HostError("repo host adapter not configured")

    def set_issue_title(self, project: HostProject, number: int, title: str) -> None:
        raise HostError("repo host adapter not configured")

    def add_issue_label(self, project: HostProject, number: int, label: str) -> None:
        raise HostError("repo host adapter not configured")

    def comment_issue(self, project: HostProject, number: int, body: str) -> None:
        raise HostError("repo host adapter not configured")

    def issue_comments(self, project: HostProject, number: int) -> list[IssueComment]:
        raise HostError("repo host adapter not configured")
