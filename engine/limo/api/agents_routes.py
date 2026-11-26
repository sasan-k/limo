from fastapi import APIRouter

from limo.agents.models import Agent
from limo.agents.registry import AgentRegistry


def agents_router(registry: AgentRegistry) -> APIRouter:
    router = APIRouter(prefix="/api/agents")

    @router.get("", response_model=list[Agent])
    def list_agents() -> list[Agent]:
        return registry.list()

    return router
