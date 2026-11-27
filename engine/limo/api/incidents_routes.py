from typing import Annotated

from fastapi import APIRouter, Path

from limo.incidents.models import Incident
from limo.runner.service import RunnerService


def incidents_router(runner: RunnerService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/projects/{name}/features/{feature}/incidents", response_model=list[Incident])
    def incidents(
        name: str, feature: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]
    ) -> list[Incident]:
        return runner.incidents(name, feature)

    return router
