from dataclasses import dataclass

from fastapi import FastAPI

from limo.agents.registry import AgentRegistry
from limo.api.agents_routes import agents_router
from limo.api.errors import install_error_handlers
from limo.api.projects_routes import projects_router
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.executor.ports import Executor
from limo.projects.repo import ProjectRepo
from limo.projects.service import ProjectService
from limo.store.db import migrate


@dataclass(frozen=True)
class Deps:
    executor: Executor


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    deps = deps or Deps(executor=LocalExecutor())
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    migrate(settings.db_path)
    projects = ProjectService(
        ProjectRepo(settings.db_path), deps.executor, settings.workspaces_dir, settings.command_timeout_s
    )
    app = FastAPI(title="Limo", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None)
    install_error_handlers(app)
    app.include_router(projects_router(projects))
    app.include_router(agents_router(AgentRegistry(settings.skills_dir)))
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())
