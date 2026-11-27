from fastapi import APIRouter

from limo.runner.loop import RunnerLoop
from limo.runner.models import RunnerSwitch, RunnerSwitchIn


def switch_router(loop: RunnerLoop) -> APIRouter:
    router = APIRouter(prefix="/api/runner")

    @router.get("", response_model=RunnerSwitch)
    def get_switch() -> RunnerSwitch:
        return RunnerSwitch(enabled=loop.enabled)

    @router.put("", response_model=RunnerSwitch)
    def set_switch(body: RunnerSwitchIn) -> RunnerSwitch:
        return RunnerSwitch(enabled=loop.set_enabled(body.enabled))

    return router
