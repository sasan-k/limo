from pathlib import Path

from limo.common.errors import ExternalError
from limo.hosts.ports import HostError, HostProject, RepoHost, ReviewComment
from limo.hosts.repo import MergeRequestRepo, NewMr
from limo.projects.models import Project
from limo.runner.models import PollResult
from limo.runner.tickets import TicketBoard, TicketRef
from limo.vcs.git import GitError, GitOps


def _new_since(comments: list[ReviewComment], last_review_id: str) -> list[ReviewComment]:
    if not last_review_id:
        return list(comments)
    ids = [c.id for c in comments]
    if last_review_id not in ids:
        return list(comments)
    return comments[ids.index(last_review_id) + 1 :]


def _write_review(workspace: Path, feature: str, ticket: str, comments: list[ReviewComment]) -> None:
    reports = workspace / "work" / feature / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    k = len(list(reports.glob(f"{ticket}-review-*.md"))) + 1
    (reports / f"{ticket}-review-{k}.md").write_text("".join(f"- {c.body}\n" for c in comments))


class ShippingService:
    def __init__(self, git: GitOps, host: RepoHost, mrs: MergeRequestRepo, board: TicketBoard) -> None:
        self._git = git
        self._host = host
        self._mrs = mrs
        self._board = board

    def needs_ship(self, project_id: str, feature: str, ticket: str) -> bool:
        mr = self._mrs.open_for_ticket(project_id, feature, ticket)
        return mr is None or mr.needs_push

    def ship(self, project: Project, feature: str, ticket: str) -> None:
        branch = f"limo/{feature}/{ticket}"
        try:
            self._git.start_ticket(Path(project.workspace), branch, project.default_branch)
            self._git.commit_and_push(Path(project.workspace), branch, f"{ticket}: {feature}")
        except GitError as e:
            raise ExternalError("git_failed", "git command failed") from e
        mr = self._mrs.open_for_ticket(project.id, feature, ticket)
        if mr is not None:
            self._mrs.set_needs_push(mr.id, False)
            return
        host_project = HostProject(project.name, project.git_url, project.host)
        try:
            ref = self._host.open_merge_request(
                host_project, branch, project.default_branch, f"{ticket} ({feature})"
            )
            self._host.enable_auto_merge(host_project, ref.number)
        except HostError as e:
            raise ExternalError("host_error", "repo host call failed") from e
        self._mrs.add(NewMr(project.id, feature, ticket, branch), ref)

    def poll(self, project: Project, feature: str) -> PollResult:
        workspace = Path(project.workspace)
        host_project = HostProject(project.name, project.git_url, project.host)
        merged: list[str] = []
        changes_requested: list[str] = []
        for mr in self._mrs.open_for(project.id, feature):
            try:
                status = self._host.merge_request_status(host_project, mr.number)
            except HostError as e:
                raise ExternalError("host_error", "repo host call failed") from e
            ref = TicketRef(workspace, project.name, feature, mr.ticket)
            if status.state == "merged":
                self._mrs.set_state(mr.id, "merged")
                self._board.set_status(ref, "done")
                merged.append(mr.ticket)
                continue
            new = _new_since(status.change_requests, mr.last_review_id)
            if not new:
                continue
            _write_review(workspace, feature, mr.ticket, new)
            self._board.set_status(ref, "todo")
            self._mrs.set_review(mr.id, new[-1].id, True)
            changes_requested.append(mr.ticket)
        return PollResult(merged=merged, changes_requested=changes_requested)
