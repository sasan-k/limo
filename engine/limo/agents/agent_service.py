from limo.agents.models import Agent
from limo.agents.registry import AgentRegistry
from limo.agents.settings_repo import AgentSettingsRepo
from limo.common.constants import AGENT_NAMES
from limo.common.errors import NotFound


class AgentService:
    def __init__(
        self, registry: AgentRegistry, settings: AgentSettingsRepo, defaults: dict[str, str]
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._defaults = defaults

    def list(self) -> list[Agent]:
        models = self._settings.all()
        return [
            agent.model_copy(update={"model": models.get(agent.name, self._defaults[agent.name])})
            for agent in self._registry.list()
        ]

    def set_model(self, name: str, model: str) -> Agent:
        if name not in AGENT_NAMES:
            raise NotFound("agent_not_found", f"agent {name} not found")
        self._settings.set(name, model)
        return next(a for a in self.list() if a.name == name)
