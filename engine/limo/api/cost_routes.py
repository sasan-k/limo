from typing import Annotated

from fastapi import APIRouter, Path

from limo.cost.models import CostTotals, Price, PriceIn
from limo.cost.service import CostService


def cost_router(service: CostService) -> APIRouter:
    router = APIRouter()

    @router.put("/api/prices/{model}", response_model=Price)
    def set_price(model: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")], body: PriceIn) -> Price:
        return service.set_price(model, body)

    @router.get("/api/prices", response_model=list[Price])
    def list_prices() -> list[Price]:
        return service.list_prices()

    @router.get("/api/projects/{name}/costs", response_model=CostTotals)
    def project_costs(name: str) -> CostTotals:
        return service.totals(name)

    return router
