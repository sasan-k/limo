from fastapi import APIRouter

from limo.projects.models import Project, ProjectIn
from limo.projects.service import ProjectService


def projects_router(service: ProjectService) -> APIRouter:
    router = APIRouter(prefix="/api/projects")

    @router.post("", status_code=201, response_model=Project)
    def add_project(body: ProjectIn) -> Project:
        return service.add(body)

    @router.get("", response_model=list[Project])
    def list_projects() -> list[Project]:
        return service.list()

    return router
