import json
from pathlib import Path

from limo.board.models import Board, BoardFeature, BoardTicket
from limo.common.constants import TICKET_STATUSES
from limo.common.errors import NotFound
from limo.projects.repo import ProjectRepo
from limo.runner.tickets import TicketBoard


class BoardService:
    def __init__(self, projects: ProjectRepo, tickets: TicketBoard) -> None:
        self._projects = projects
        self._tickets = tickets

    def board(self, project_name: str) -> Board:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        workspace = Path(project.workspace)
        names = sorted(p.parent.name for p in (workspace / "work").glob("*/map.yaml"))
        features = [
            BoardFeature(
                name=name,
                tickets=[
                    BoardTicket(**t)
                    for t in json.loads(self._tickets.board_json(workspace, project.name, name))
                ],
            )
            for name in names
        ]
        return Board(project=project.name, statuses=list(TICKET_STATUSES), features=features)
