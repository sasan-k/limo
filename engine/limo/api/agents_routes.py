from fastapi import APIRouter

from limo.agents.agent_service import AgentService
from limo.agents.models import Agent, ModelIn


def agents_router(service: AgentService) -> APIRouter:
    router = APIRouter(prefix="/api/agents")

    @router.get("", response_model=list[Agent])
    def list_agents() -> list[Agent]:
        return service.list()

    @router.put("/{name}/model", response_model=Agent)
    def set_agent_model(name: str, body: ModelIn) -> Agent:
        return service.set_model(name, body.model)

    return router
