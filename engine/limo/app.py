from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from limo.agents.registry import AgentRegistry
from limo.agents.repo import RunRepo
from limo.agents.service import RunConfig, RunService, RunStores
from limo.agents.tools import ToolBox
from limo.api.agents_routes import agents_router
from limo.api.errors import install_error_handlers
from limo.api.projects_routes import projects_router
from limo.api.runs_routes import runs_router
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.executor.ports import Executor
from limo.llm.anthropic_client import AnthropicLlm
from limo.llm.ports import LlmClient
from limo.projects.repo import ProjectRepo
from limo.projects.service import ProjectService
from limo.store.db import migrate


@dataclass(frozen=True)
class Deps:
    executor: Executor
    llm: LlmClient


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    deps = deps or Deps(executor=LocalExecutor(), llm=AnthropicLlm(settings.anthropic_api_key))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    migrate(settings.db_path)
    projects = ProjectService(
        ProjectRepo(settings.db_path), deps.executor, settings.workspaces_dir, settings.command_timeout_s
    )
    runs = RunService(
        RunStores(RunRepo(settings.db_path), ProjectRepo(settings.db_path)),
        deps.llm,
        ToolBox(deps.executor, settings.command_timeout_s),
        RunConfig(settings.skills_dir, settings.default_model, settings.max_turns),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        runs.close()

    app = FastAPI(
        title="Limo", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None, lifespan=lifespan
    )
    install_error_handlers(app)
    app.include_router(projects_router(projects))
    app.include_router(agents_router(AgentRegistry(settings.skills_dir)))
    app.include_router(runs_router(runs))
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())
