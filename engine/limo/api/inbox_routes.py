from fastapi import APIRouter

from limo.inbox.models import ContinueIn, InboxItem
from limo.runner.models import StepResult
from limo.runner.service import RunnerService


def inbox_router(runner: RunnerService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/inbox", response_model=list[InboxItem])
    def list_inbox() -> list[InboxItem]:
        return runner.inbox()

    @router.post("/api/inbox/{item_id}/continue", response_model=StepResult)
    def continue_item(item_id: str, body: ContinueIn | None = None) -> StepResult:
        return runner.continue_item(item_id, body.response if body else None)

    return router
