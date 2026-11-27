from typing import Annotated

from fastapi import APIRouter, Path

from limo.budget.models import BudgetIn, Defaults, DefaultsIn, TicketBudget
from limo.budget.service import BudgetService

FEATURE = r"^[a-z0-9][a-z0-9-]{0,39}$"
TICKET = r"^TKT-\d+$"


def budget_router(service: BudgetService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/budgets/defaults", response_model=Defaults)
    def get_defaults() -> Defaults:
        return service.get_defaults()

    @router.put("/api/budgets/defaults", response_model=Defaults)
    def set_defaults(body: DefaultsIn) -> Defaults:
        return service.set_defaults(body)

    @router.get(
        "/api/projects/{name}/features/{feature}/tickets/{ticket}/budget", response_model=TicketBudget
    )
    def get_budget(
        name: str,
        feature: Annotated[str, Path(pattern=FEATURE)],
        ticket: Annotated[str, Path(pattern=TICKET)],
    ) -> TicketBudget:
        return service.status(name, feature, ticket)

    @router.put(
        "/api/projects/{name}/features/{feature}/tickets/{ticket}/budget", response_model=TicketBudget
    )
    def set_budget(
        name: str,
        feature: Annotated[str, Path(pattern=FEATURE)],
        ticket: Annotated[str, Path(pattern=TICKET)],
        body: BudgetIn,
    ) -> TicketBudget:
        return service.set_budget(name, feature, ticket, body)

    return router
