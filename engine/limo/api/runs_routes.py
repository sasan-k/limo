from fastapi import APIRouter

from limo.agents.models import Run, RunIn, ToolCall
from limo.agents.service import RunService


def runs_router(service: RunService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/projects/{name}/runs", status_code=202, response_model=Run)
    def start_run(name: str, body: RunIn) -> Run:
        return service.start(name, body)

    @router.get("/api/runs/{run_id}", response_model=Run)
    def get_run(run_id: str) -> Run:
        return service.get(run_id)

    @router.get("/api/runs/{run_id}/tool-calls", response_model=list[ToolCall])
    def list_tool_calls(run_id: str) -> list[ToolCall]:
        return service.tool_calls(run_id)

    return router
