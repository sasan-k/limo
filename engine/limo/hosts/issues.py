from pathlib import Path

from limo.common.errors import ExternalError
from limo.hosts.issue_repo import IssueRepo, IssueRow
from limo.hosts.ports import HostError, HostProject, RepoHost
from limo.projects.models import Project
from limo.runner.tickets import TicketBoard, TicketState

FINISHED = ("done", "abandoned")


class IssueService:
    def __init__(self, host: RepoHost, repo: IssueRepo, board: TicketBoard) -> None:
        self._host = host
        self._repo = repo
        self._board = board

    def sync(self, project: Project, feature: str, states: list[TicketState]) -> None:
        rows = self._repo.for_feature(project.id, feature)
        titles: dict[str, str] = {}
        if any(state.id not in rows for state in states):
            titles = self._board.titles(Path(project.workspace), project.name, feature)
        hp = HostProject(name=project.name, git_url=project.git_url, kind=project.host)
        try:
            for state in states:
                row = rows.get(state.id)
                if row is None and state.status in FINISHED:
                    continue  # finished before Limo tracked it (e.g. an adopted repo): no issue
                if row is None:
                    ref = self._host.create_issue(hp, f"{state.id}: {titles[state.id]}")
                    self._host.set_issue_status(hp, ref.number, state.status)
                    self._repo.add(
                        project.id,
                        feature,
                        IssueRow(ticket=state.id, number=ref.number, url=ref.url, status=state.status),
                    )
                elif row.status != state.status:
                    self._host.set_issue_status(hp, row.number, state.status)
                    self._repo.set_status(project.id, feature, state.id, state.status)
        except HostError as e:
            raise ExternalError("host_error", "repo host call failed") from e
