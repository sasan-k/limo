from fastapi import APIRouter

from limo.features.models import Feature, FeatureIn
from limo.features.service import FeatureService


def features_router(service: FeatureService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/projects/{name}/features", status_code=201, response_model=Feature)
    def create(name: str, data: FeatureIn) -> Feature:
        return service.create(name, data)

    @router.get("/api/projects/{name}/features", response_model=list[Feature])
    def list_features(name: str) -> list[Feature]:
        return service.list(name)

    return router
