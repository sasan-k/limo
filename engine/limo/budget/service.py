from limo.budget.models import BudgetIn, Defaults, DefaultsIn, Line, TicketBudget
from limo.budget.repo import BudgetKey, BudgetRepo
from limo.common.constants import AGENT_NAMES
from limo.common.errors import NotFound
from limo.cost.pricing import format_usd, to_micros
from limo.cost.repo import UsageRepo
from limo.cost.service import CallRef
from limo.projects.models import Project
from limo.projects.repo import ProjectRepo


def _dollars(micros: int) -> str:
    cents = (micros + 5_000) // 10_000
    return f"${cents // 100}.{cents % 100:02d}"


class BudgetService:
    def __init__(
        self, repo: BudgetRepo, usage: UsageRepo, projects: ProjectRepo, fallback: tuple[int, int]
    ) -> None:
        self._repo = repo
        self._usage = usage
        self._projects = projects
        self._fallback = fallback

    def get_defaults(self) -> Defaults:
        stored = self._repo.defaults()
        ticket, agent = self._fallback if stored is None else stored
        return Defaults(ticket=format_usd(ticket), agent=format_usd(agent))

    def set_defaults(self, data: DefaultsIn) -> Defaults:
        self._repo.set_defaults(to_micros(data.ticket), to_micros(data.agent))
        return self.get_defaults()

    def status(self, project_name: str, feature: str, ticket: str) -> TicketBudget:
        project = self._project(project_name)
        ticket_limit, agent_limits = self._limits(BudgetKey(project.id, feature, ticket))
        ticket_spent = self._usage.ticket_spent(project.id, feature, ticket)
        agent_spent = self._usage.agent_spent(project.id, feature, ticket)
        return TicketBudget(
            ticket=Line(budget=format_usd(ticket_limit), spent=format_usd(ticket_spent)),
            agents={
                agent: Line(
                    budget=format_usd(agent_limits[agent]),
                    spent=format_usd(agent_spent.get(agent, 0)),
                )
                for agent in AGENT_NAMES
            },
        )

    def set_budget(self, project_name: str, feature: str, ticket: str, data: BudgetIn) -> TicketBudget:
        project = self._project(project_name)
        key = BudgetKey(project.id, feature, ticket)
        self._repo.set_override(key, data.agent or "", to_micros(data.amount))
        return self.status(project_name, feature, ticket)

    def exceeded(self, ref: CallRef) -> str | None:
        if ref.ticket is None:
            return None
        ticket_limit, agent_limits = self._limits(BudgetKey(ref.project_id, ref.feature, ref.ticket))
        ticket_spent = self._usage.ticket_spent(ref.project_id, ref.feature, ref.ticket)
        if ticket_spent >= ticket_limit:
            return f"ticket budget reached: {_dollars(ticket_spent)} of {_dollars(ticket_limit)}"
        agent_limit = agent_limits[ref.agent]
        agent_spent = self._usage.agent_spent(ref.project_id, ref.feature, ref.ticket).get(ref.agent, 0)
        if agent_spent >= agent_limit:
            return f"{ref.agent} budget reached: {_dollars(agent_spent)} of {_dollars(agent_limit)}"
        return None

    def remaining_usd(self, ref: CallRef) -> float | None:
        """Budget left for this agent on this ticket (the lower of ticket and agent), in USD."""
        if ref.ticket is None:
            return None
        ticket_limit, agent_limits = self._limits(BudgetKey(ref.project_id, ref.feature, ref.ticket))
        ticket_left = ticket_limit - self._usage.ticket_spent(ref.project_id, ref.feature, ref.ticket)
        agent_spent = self._usage.agent_spent(ref.project_id, ref.feature, ref.ticket).get(ref.agent, 0)
        agent_left = agent_limits[ref.agent] - agent_spent
        return max(0, min(ticket_left, agent_left)) / 1_000_000

    def _project(self, project_name: str) -> Project:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        return project

    def _limits(self, key: BudgetKey) -> tuple[int, dict[str, int]]:
        stored = self._repo.defaults()
        ticket_default, agent_default = self._fallback if stored is None else stored
        overrides = self._repo.overrides(key.project_id, key.feature, key.ticket)
        ticket_limit = overrides.get("", ticket_default)
        agent_limits = {agent: overrides.get(agent, agent_default) for agent in AGENT_NAMES}
        return ticket_limit, agent_limits
