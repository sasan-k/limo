from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from limo.agents.agent_service import AgentService
from limo.agents.registry import AgentRegistry
from limo.agents.repo import RunRepo
from limo.agents.service import RunConfig, RunService, RunStores
from limo.agents.settings_repo import AgentSettingsRepo
from limo.agents.tools import ToolBox
from limo.api.agents_routes import agents_router
from limo.api.budget_routes import budget_router
from limo.api.cost_routes import cost_router
from limo.api.errors import install_error_handlers
from limo.api.features_routes import features_router
from limo.api.inbox_routes import inbox_router
from limo.api.incidents_routes import incidents_router
from limo.api.projects_routes import projects_router
from limo.api.runner_routes import runner_router
from limo.api.runs_routes import runs_router
from limo.budget.repo import BudgetRepo
from limo.budget.service import BudgetService
from limo.config import Settings
from limo.cost.pricing import to_micros
from limo.cost.repo import PriceRepo, UsageRepo
from limo.cost.service import CostService
from limo.executor.local import LocalExecutor
from limo.executor.ports import Executor
from limo.features.phases import PhaseService
from limo.features.repo import FeatureRepo
from limo.features.service import FeatureService
from limo.hosts.issue_repo import IssueRepo
from limo.hosts.issues import IssueService
from limo.hosts.ports import RepoHost
from limo.hosts.repo import MergeRequestRepo
from limo.hosts.unconfigured import UnconfiguredHost
from limo.inbox.repo import HoldRepo
from limo.inbox.service import InboxService
from limo.incidents.apply import ActionApplier
from limo.incidents.repo import IncidentRepo
from limo.incidents.service import IncidentDeps, IncidentService
from limo.llm.anthropic_client import AnthropicLlm
from limo.llm.ports import LlmClient
from limo.projects.repo import ProjectRepo
from limo.projects.service import ProjectService
from limo.runner.service import RunnerDeps, RunnerService
from limo.runner.shipping import ShippingService
from limo.runner.tickets import TicketBoard
from limo.store.db import migrate
from limo.vcs.git import GitOps


@dataclass(frozen=True)
class Deps:
    executor: Executor
    llm: LlmClient
    host: RepoHost | None = None


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    deps = deps or Deps(
        executor=LocalExecutor(path_prefix=settings.scripts_dir),
        llm=AnthropicLlm(settings.anthropic_api_key),
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    migrate(settings.db_path)
    projects = ProjectService(
        ProjectRepo(settings.db_path), deps.executor, settings.workspaces_dir, settings.command_timeout_s
    )
    agent_settings = AgentSettingsRepo(settings.db_path)
    usage = UsageRepo(settings.db_path)
    cost = CostService(PriceRepo(settings.db_path), usage, ProjectRepo(settings.db_path))
    budget = BudgetService(
        BudgetRepo(settings.db_path),
        usage,
        ProjectRepo(settings.db_path),
        (to_micros(settings.default_ticket_budget), to_micros(settings.default_agent_budget)),
    )
    inbox = InboxService(HoldRepo(settings.db_path))
    feature_repo = FeatureRepo(settings.db_path)
    features = FeatureService(feature_repo, ProjectRepo(settings.db_path))
    runs = RunService(
        RunStores(
            RunRepo(settings.db_path),
            ProjectRepo(settings.db_path),
            agent_settings,
            cost,
            budget,
            inbox,
        ),
        deps.llm,
        ToolBox(deps.executor, settings.command_timeout_s),
        RunConfig(settings.skills_dir, settings.default_model, settings.max_turns, fx_db=settings.db_path),
    )
    board = TicketBoard(deps.executor, settings.db_path, settings.command_timeout_s)
    git = GitOps(deps.executor, settings.command_timeout_s)
    shipping = ShippingService(
        git, deps.host or UnconfiguredHost(), MergeRequestRepo(settings.db_path), board
    )
    incident_repo = IncidentRepo(settings.db_path)
    host = deps.host or UnconfiguredHost()
    applier = ActionApplier(board, host, IssueRepo(settings.db_path), incident_repo)
    runner = RunnerService(
        RunnerDeps(
            runs,
            ProjectRepo(settings.db_path),
            board,
            inbox,
            shipping,
            git,
            PhaseService(feature_repo, runs, board),
            IssueService(deps.host or UnconfiguredHost(), IssueRepo(settings.db_path), board),
            IncidentService(IncidentDeps(incident_repo, runs, board, applier), settings.run_timeout_s),
        ),
        settings.max_concurrent_tickets,
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
    app.include_router(
        agents_router(
            AgentService(AgentRegistry(settings.skills_dir), agent_settings, settings.default_model)
        )
    )
    app.include_router(runs_router(runs))
    app.include_router(cost_router(cost))
    app.include_router(runner_router(runner))
    app.include_router(incidents_router(runner))
    app.include_router(budget_router(budget))
    app.include_router(inbox_router(inbox, runner))
    app.include_router(features_router(features))
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())
