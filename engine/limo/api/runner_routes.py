from typing import Annotated

from fastapi import APIRouter, Path

from limo.runner.models import PollResult, StepResult
from limo.runner.service import RunnerService


def runner_router(service: RunnerService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/projects/{name}/features/{feature}/step", response_model=StepResult)
    def step(name: str, feature: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]) -> StepResult:
        return service.step(name, feature)

    @router.post("/api/projects/{name}/features/{feature}/poll", response_model=PollResult)
    def poll(name: str, feature: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]) -> PollResult:
        return service.poll(name, feature)

    return router
