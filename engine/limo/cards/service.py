from datetime import datetime

from limo.agents.settings_repo import AgentSettingsRepo
from limo.cards.models import AgentCard, AgentState, LastRun
from limo.cards.repo import CardRepo, CardRow
from limo.common.constants import AGENT_NAMES
from limo.cost.pricing import format_usd


class AgentCardService:
    def __init__(self, repo: CardRepo, settings: AgentSettingsRepo, defaults: dict[str, str]) -> None:
        self._repo = repo
        self._settings = settings
        self._defaults = defaults

    def list(self) -> list[AgentCard]:
        rows = {r.agent: r for r in self._repo.latest_runs()}
        models = self._settings.all()
        return [_card(name, models.get(name, self._defaults[name]), rows.get(name)) for name in AGENT_NAMES]


def _card(agent: str, model: str, row: CardRow | None) -> AgentCard:
    if row is None:
        return AgentCard(
            agent=agent,
            model=model,
            state="idle",
            project=None,
            feature=None,
            ticket=None,
            cost=format_usd(0),
            last_run=None,
        )
    return AgentCard(
        agent=agent,
        model=model,
        state=_state(row),
        project=row.project,
        feature=row.feature,
        ticket=row.ticket,
        cost=format_usd(row.cost_micros),
        last_run=LastRun(
            id=row.run_id,
            status=row.status,
            tokens=row.tokens,
            started_at=row.created_at,
            finished_at=row.finished_at,
            duration_s=_duration(row),
            tries=row.attempt,
        ),
    )


def _state(row: CardRow) -> AgentState:
    if row.status in ("queued", "running"):
        return "active"
    if row.has_incident and row.agent != "resolver":
        return "stuck"
    return "idle"


def _duration(row: CardRow) -> int | None:
    if row.finished_at is None:
        return None
    elapsed = datetime.fromisoformat(row.finished_at) - datetime.fromisoformat(row.created_at)
    return int(elapsed.total_seconds())
