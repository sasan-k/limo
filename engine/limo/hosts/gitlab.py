from typing import Literal
from urllib.parse import quote

from limo.hosts.http import HttpHost
from limo.hosts.ports import HostProject, IssueComment, IssueRef, MergeRequestRef, MrStatus, ReviewComment

_LIMO_PREFIX = "limo:"


class GitLabHost(HttpHost):
    label = "gitlab"
    user_field = "username"

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"PRIVATE-TOKEN": token}

    def _project(self, project: HostProject) -> str:
        return quote(self._repo(project), safe="")

    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        data = self._request(
            "POST",
            f"/projects/{self._project(project)}/merge_requests",
            {"source_branch": branch, "target_branch": base, "title": title},
        )
        return MergeRequestRef(number=data["iid"], url=data["web_url"])

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        self._request(
            "PUT",
            f"/projects/{self._project(project)}/merge_requests/{number}/merge",
            {"merge_when_pipeline_succeeds": True},
        )

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        base = f"/projects/{self._project(project)}/merge_requests/{number}"
        mr = self._request("GET", base)
        approvals = self._request("GET", f"{base}/approvals")
        notes = self._request("GET", f"{base}/notes?sort=asc")
        me = self._me()
        state: Literal["open", "merged", "closed"]
        if mr["state"] == "merged":
            state = "merged"
        elif mr["state"] == "opened":
            state = "open"
        else:
            state = "closed"
        changes = [
            ReviewComment(str(note["id"]), note["body"])
            for note in notes
            if not note["system"] and note["author"]["username"] != me
        ]
        return MrStatus(state=state, approved=bool(approvals["approved"]), change_requests=changes)

    def create_issue(self, project: HostProject, title: str) -> IssueRef:
        data = self._request("POST", f"/projects/{self._project(project)}/issues", {"title": title})
        return IssueRef(number=data["iid"], url=data["web_url"])

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None:
        path = f"/projects/{self._project(project)}/issues/{number}"
        new_label = f"{_LIMO_PREFIX}{status}"
        issue = self._request("GET", path)
        others = [label for label in issue["labels"] if label.startswith(_LIMO_PREFIX) and label != new_label]
        self._request("PUT", path, {"add_labels": new_label, "remove_labels": ",".join(others)})

    def set_issue_title(self, project: HostProject, number: int, title: str) -> None:
        self._request("PUT", f"/projects/{self._project(project)}/issues/{number}", {"title": title})

    def add_issue_label(self, project: HostProject, number: int, label: str) -> None:
        self._request("PUT", f"/projects/{self._project(project)}/issues/{number}", {"add_labels": label})

    def comment_issue(self, project: HostProject, number: int, body: str) -> None:
        self._request("POST", f"/projects/{self._project(project)}/issues/{number}/notes", {"body": body})

    def issue_comments(self, project: HostProject, number: int) -> list[IssueComment]:
        path = f"/projects/{self._project(project)}/issues/{number}/notes?sort=asc"
        notes = self._request("GET", path)
        me = self._me()
        return [
            IssueComment(str(note["id"]), note["body"], note["author"]["username"] == me)
            for note in notes
            if not note["system"]
        ]
