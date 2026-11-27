from limo.common.errors import Conflict, NotFound
from limo.inbox.models import Hold
from limo.inbox.repo import HoldRepo, NewHold


class InboxService:
    def __init__(self, repo: HoldRepo) -> None:
        self._repo = repo

    def hold(self, hold: NewHold) -> None:
        self._repo.add(hold)

    def list(self) -> list[Hold]:
        return self._repo.open_list()

    def has(self, hold_id: str) -> bool:
        return self._repo.get(hold_id) is not None

    def take(self, hold_id: str) -> Hold:
        found = self._repo.get(hold_id)
        if found is None:
            raise NotFound("hold_not_found", f"hold {hold_id} not found")
        hold, cleared_at = found
        if cleared_at is not None:
            raise Conflict("hold_cleared", f"hold {hold_id} already continued")
        self._repo.clear(hold_id)
        return hold

    def held_tickets(self, project_id: str, feature: str) -> set[str]:
        return self._repo.open_tickets(project_id, feature)
