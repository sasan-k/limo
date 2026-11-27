from fastapi import APIRouter

from limo.inbox.models import Hold
from limo.inbox.service import InboxService
from limo.runner.models import StepResult
from limo.runner.service import RunnerService


def inbox_router(inbox: InboxService, runner: RunnerService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/inbox", response_model=list[Hold])
    def list_holds() -> list[Hold]:
        return inbox.list()

    @router.post("/api/inbox/{hold_id}/continue", response_model=StepResult)
    def continue_hold(hold_id: str) -> StepResult:
        return runner.continue_hold(hold_id)

    return router
