from dataclasses import dataclass

from limo.common.errors import NotFound
from limo.cost.models import AgentTicketCost, CostTotals, Price, PriceIn, TokenCounts
from limo.cost.pricing import PriceMicros, cost_micros, format_usd, to_micros
from limo.cost.repo import PriceRepo, UsageRepo, UsageRow
from limo.llm.ports import LlmUsage
from limo.projects.repo import ProjectRepo


@dataclass(frozen=True)
class CallRef:
    run_id: str
    project_id: str
    agent: str
    feature: str
    ticket: str | None


class CostService:
    def __init__(self, prices: PriceRepo, usage: UsageRepo, projects: ProjectRepo) -> None:
        self._prices = prices
        self._usage = usage
        self._projects = projects

    def set_price(self, model: str, data: PriceIn) -> Price:
        self._prices.set(
            model,
            PriceMicros(
                to_micros(data.input),
                to_micros(data.output),
                to_micros(data.cache_read),
                to_micros(data.cache_write),
            ),
        )
        return self._to_price(model, self._prices.get(model))

    def list_prices(self) -> list[Price]:
        return [self._to_price(model, price) for model, price in self._prices.list()]

    def record(self, ref: CallRef, seq: int, model: str, usage: LlmUsage) -> None:
        price = self._prices.get(model)
        self._usage.add(
            UsageRow(
                run_id=ref.run_id,
                project_id=ref.project_id,
                agent=ref.agent,
                feature=ref.feature,
                ticket=ref.ticket,
                seq=seq,
                model=model,
                usage=usage,
                cost_micros=cost_micros(usage, price),
                priced=price is not None,
            )
        )

    def run_summary(self, run_id: str) -> tuple[TokenCounts, str]:
        tokens, micros = self._usage.run_sum(run_id)
        return tokens, format_usd(micros)

    def totals(self, project_name: str) -> CostTotals:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        per_agent: dict[str, int] = {}
        per_ticket: dict[str, int] = {}
        per_pair: list[AgentTicketCost] = []
        overall = 0
        for agent, ticket, micros in self._usage.project_rows(project.id):
            key = ticket or "none"
            per_agent[agent] = per_agent.get(agent, 0) + micros
            per_ticket[key] = per_ticket.get(key, 0) + micros
            per_pair.append(AgentTicketCost(agent=agent, ticket=key, cost=format_usd(micros)))
            overall += micros
        return CostTotals(
            per_agent={agent: format_usd(m) for agent, m in per_agent.items()},
            per_ticket={ticket: format_usd(m) for ticket, m in per_ticket.items()},
            per_agent_ticket=per_pair,
            overall=format_usd(overall),
        )

    @staticmethod
    def _to_price(model: str, price: PriceMicros | None) -> Price:
        if price is None:
            return Price(
                model=model,
                input="0.000000",
                output="0.000000",
                cache_read="0.000000",
                cache_write="0.000000",
            )
        return Price(
            model=model,
            input=format_usd(price.input),
            output=format_usd(price.output),
            cache_read=format_usd(price.cache_read),
            cache_write=format_usd(price.cache_write),
        )
