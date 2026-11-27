from typing import Literal
from urllib.parse import quote

from limo.hosts.http import HttpHost
from limo.hosts.ports import (
    HostError,
    HostProject,
    IssueComment,
    IssueRef,
    MergeRequestRef,
    MrStatus,
    ReviewComment,
)

_LIMO_PREFIX = "limo:"


class GitHubHost(HttpHost):
    label = "github"
    user_field = "login"

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    def open_merge_request(self, project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef:
        data = self._request(
            "POST", f"/repos/{self._repo(project)}/pulls", {"title": title, "head": branch, "base": base}
        )
        return MergeRequestRef(number=data["number"], url=data["html_url"])

    def enable_auto_merge(self, project: HostProject, number: int) -> None:
        pull = self._request("GET", f"/repos/{self._repo(project)}/pulls/{number}")
        query = (
            "mutation($id: ID!) { enablePullRequestAutoMerge("
            "input: {pullRequestId: $id, mergeMethod: MERGE}) { clientMutationId } }"
        )
        result = self._request("POST", "/graphql", {"query": query, "variables": {"id": pull["node_id"]}})
        if result.get("errors"):
            raise HostError("github POST /graphql failed: errors")

    def merge_request_status(self, project: HostProject, number: int) -> MrStatus:
        base = f"/repos/{self._repo(project)}/pulls/{number}"
        pull = self._request("GET", base)
        reviews = self._request("GET", f"{base}/reviews")
        state: Literal["open", "merged", "closed"]
        if pull["merged"]:
            state = "merged"
        elif pull["state"] == "open":
            state = "open"
        else:
            state = "closed"
        approved = any(review["state"] == "APPROVED" for review in reviews)
        changes = [
            ReviewComment(str(review["id"]), review["body"])
            for review in reviews
            if review["state"] == "CHANGES_REQUESTED"
        ]
        return MrStatus(state=state, approved=approved, change_requests=changes)

    def create_issue(self, project: HostProject, title: str) -> IssueRef:
        data = self._request("POST", f"/repos/{self._repo(project)}/issues", {"title": title})
        return IssueRef(number=data["number"], url=data["html_url"])

    def set_issue_status(self, project: HostProject, number: int, status: str) -> None:
        base = f"/repos/{self._repo(project)}/issues/{number}"
        new_label = f"{_LIMO_PREFIX}{status}"
        for label in self._request("GET", f"{base}/labels"):
            name = label["name"]
            if name.startswith(_LIMO_PREFIX) and name != new_label:
                self._request("DELETE", f"{base}/labels/{quote(name, safe=':')}")
        self._request("POST", f"{base}/labels", {"labels": [new_label]})

    def set_issue_title(self, project: HostProject, number: int, title: str) -> None:
        self._request("PATCH", f"/repos/{self._repo(project)}/issues/{number}", {"title": title})

    def add_issue_label(self, project: HostProject, number: int, label: str) -> None:
        base = f"/repos/{self._repo(project)}/issues/{number}"
        self._request("POST", f"{base}/labels", {"labels": [label]})

    def comment_issue(self, project: HostProject, number: int, body: str) -> None:
        base = f"/repos/{self._repo(project)}/issues/{number}"
        self._request("POST", f"{base}/comments", {"body": body})

    def issue_comments(self, project: HostProject, number: int) -> list[IssueComment]:
        base = f"/repos/{self._repo(project)}/issues/{number}"
        comments = self._request("GET", f"{base}/comments")
        me = self._me()
        return [
            IssueComment(str(comment["id"]), comment["body"], comment["user"]["login"] == me)
            for comment in comments
        ]
