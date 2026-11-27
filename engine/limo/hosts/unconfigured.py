from limo.hosts.ports import HostError, HostProject, MergeRequestRef, MrStatus


class UnconfiguredHost:
    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        raise HostError("repo host adapter not configured")

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        raise HostError("repo host adapter not configured")

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        raise HostError("repo host adapter not configured")
