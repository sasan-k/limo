from fastapi import APIRouter

from limo.cards.models import AgentCard
from limo.cards.service import AgentCardService


def cards_router(service: AgentCardService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/agent-cards", response_model=list[AgentCard])
    def list_agent_cards() -> list[AgentCard]:
        return service.list()

    return router
