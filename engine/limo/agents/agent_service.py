from limo.agents.models import Agent
from limo.agents.registry import AgentRegistry
from limo.agents.settings_repo import AgentSettingsRepo
from limo.common.constants import AGENT_NAMES
from limo.common.errors import NotFound


class AgentService:
    def __init__(self, registry: AgentRegistry, settings: AgentSettingsRepo, default_model: str) -> None:
        self._registry = registry
        self._settings = settings
        self._default_model = default_model

    def list(self) -> list[Agent]:
        models = self._settings.all()
        return [
            agent.model_copy(update={"model": models.get(agent.name, self._default_model)})
            for agent in self._registry.list()
        ]

    def model_for(self, agent: str) -> str:
        return self._settings.get(agent) or self._default_model

    def set_model(self, name: str, model: str) -> Agent:
        if name not in AGENT_NAMES:
            raise NotFound("agent_not_found", f"agent {name} not found")
        self._settings.set(name, model)
        return next(a for a in self.list() if a.name == name)
