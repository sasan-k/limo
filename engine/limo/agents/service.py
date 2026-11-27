from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from limo.agents.cli_runner import CliRunner
from limo.agents.context_pack import parse_context_pack
from limo.agents.models import Run, RunIn, ToolCall
from limo.agents.repo import RunRepo
from limo.agents.settings_repo import AgentSettingsRepo
from limo.agents.tools import ToolBox, ToolContext, ToolOutcome
from limo.budget.service import BudgetService
from limo.common.errors import NotFound
from limo.cost.service import CallRef, CostService
from limo.events.bus import EventBus
from limo.inbox.repo import NewHold
from limo.inbox.service import InboxService
from limo.llm.ports import LlmClient, LlmError, LlmRequest
from limo.projects.repo import ProjectRepo


def _payload(run: Run) -> dict[str, object]:
    return {"run_id": run.id, "agent": run.agent, "feature": run.feature, "ticket": run.ticket}


def _task(run: Run) -> str:
    """The run's task message: feature, ticket, args and the replan note."""
    task = f"feature={run.feature}"
    if run.ticket:
        task += f" ticket={run.ticket}"
    if run.args:
        task += f" {run.args}"
    if run.note:
        task += f"\nnote: {run.note}"
    return task


@dataclass(frozen=True)
class RunStores:
    runs: RunRepo
    projects: ProjectRepo
    agent_settings: AgentSettingsRepo
    cost: CostService
    budget: BudgetService
    inbox: InboxService


@dataclass(frozen=True)
class RunConfig:
    skills_dir: Path
    model: str
    max_turns: int
    fx_db: Path
    backend: str = "api"


@dataclass(frozen=True)
class Backends:
    """How runs talk to Claude: the Messages API loop (ADR-6) or local `claude -p` sessions (ADR-14)."""

    llm: LlmClient
    cli: CliRunner | None = None


class RunService:
    def __init__(
        self, stores: RunStores, backends: Backends, tools: ToolBox, config: RunConfig, events: EventBus
    ) -> None:
        self._stores = stores
        self._llm = backends.llm
        self._cli = backends.cli
        self._tools = tools
        self._config = config
        self._events = events
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="limo-run")

    def close(self) -> None:
        self._pool.shutdown(wait=True, cancel_futures=True)

    def start(self, project_name: str, data: RunIn) -> Run:
        project = self._stores.projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        model = self._stores.agent_settings.get(data.agent) or self._config.model
        attempt = self._stores.runs.count_attempts(project.id, data.feature, data.ticket, data.agent) + 1
        run = Run(
            id=uuid4().hex,
            project=project_name,
            agent=data.agent,
            feature=data.feature,
            ticket=data.ticket,
            status="queued",
            model=model,
            output=None,
            error=None,
            created_at=datetime.now(UTC).isoformat(),
            finished_at=None,
            args=data.args,
            ticket_status=data.ticket_status,
            note=data.note,
            attempt=attempt,
        )
        self._stores.runs.insert(run, project.id)
        self._events.publish("run.started", project.id, _payload(run))
        self._pool.submit(self._execute, run, project.id)
        return run

    def latest(self, project_id: str, feature: str, agent: str, args: str | None) -> Run | None:
        return self._stores.runs.latest(project_id, feature, agent, args)

    def latest_for_ticket(self, project_id: str, feature: str, ticket: str) -> Run | None:
        return self._stores.runs.latest_for_ticket(project_id, feature, ticket)

    def fail_timed_out(self, project_id: str, cutoff_iso: str) -> int:
        run_ids = self._stores.runs.active_older_than(project_id, cutoff_iso)
        for run_id in run_ids:
            self._stores.runs.finish(run_id, "failed", None, "timeout")
            self._events.publish("run.finished", project_id, {"run_id": run_id})
        return len(run_ids)

    def get(self, run_id: str) -> Run:
        run = self._stores.runs.get(run_id)
        if run is None:
            raise NotFound("run_not_found", f"run {run_id} not found")
        tokens, cost = self._stores.cost.run_summary(run_id)
        return run.model_copy(update={"tokens": tokens, "cost": cost})

    def tool_calls(self, run_id: str) -> list[ToolCall]:
        self.get(run_id)
        return self._stores.runs.tool_calls(run_id)

    def active_count(self) -> int:
        return self._stores.runs.active_count()

    def _execute(self, run: Run, project_id: str) -> None:
        try:
            self._stores.runs.set_status(run.id, "running")
            self._events.publish("run.updated", project_id, _payload(run))
            self._run(run)
        except LlmError as e:
            self._stores.runs.finish(run.id, "failed", None, f"llm_error: {e}")
        except Exception as e:
            self._stores.runs.finish(run.id, "failed", None, f"internal_error: {e}")
        finally:
            self._events.publish("run.finished", project_id, _payload(run))

    def _run(self, run: Run) -> None:
        project = self._stores.projects.get_by_name(run.project)
        if project is None:
            self._stores.runs.finish(run.id, "failed", None, f"project not found: {run.project}")
            return
        ref = CallRef(run.id, project.id, run.agent, run.feature, run.ticket)
        workspace = Path(project.workspace)
        readable: dict[str, tuple[int, int] | None] | None = None
        if run.agent == "build":
            plan_rel = f"work/{run.feature}/plans/{run.ticket}.md"
            plan_path = workspace / plan_rel
            if not plan_path.is_file():
                self._stores.runs.finish(run.id, "failed", None, f"plan not found: {plan_rel}")
                return
            pack = parse_context_pack(plan_path.read_text())
            readable = {**pack, plan_rel: None, "context/INDEX.md": None}
        env = {"FX_DB": str(self._config.fx_db), "FX_SCOPE": project.name}
        ctx = ToolContext(run.agent, workspace, self._config.skills_dir / run.agent, readable, env=env)
        if self._config.backend == "claude-cli" and self._cli is not None:
            self._cli_session(run, ctx, ref, self._cli)
        else:
            self._loop(run, ctx, ref)

    def _cli_session(self, run: Run, ctx: ToolContext, ref: CallRef, cli: CliRunner) -> None:
        budget = self._stores.budget.remaining_usd(ref)
        if budget is not None and budget <= 0:
            self._stop_for_budget(run, ref, self._stores.budget.exceeded(ref) or "budget reached")
            return

        def on_event(event: dict[str, Any]) -> None:
            if event.get("type") == "assistant":
                self._events.publish("run.updated", ref.project_id, _payload(run))

        result = cli.run(run, ctx, _task(run), budget, on_event)
        self._stores.cost.record_billed(ref, 1, run.model, result.usage, result.cost_micros)
        self._events.publish("cost.updated", ref.project_id, {"run_id": run.id})
        if result.ok:
            self._stores.runs.finish(run.id, "succeeded", result.text, None)
        else:
            self._stores.runs.finish(run.id, "failed", result.text, result.error)

    def _loop(self, run: Run, ctx: ToolContext, ref: CallRef) -> None:
        system = (self._config.skills_dir / run.agent / "SKILL.md").read_text()
        messages: list[dict[str, Any]] = [{"role": "user", "content": _task(run)}]
        seq = 0
        call_no = 0
        for _ in range(self._config.max_turns):
            request = LlmRequest(run.model, system, list(messages), self._tools.specs(run.agent))
            resp = self._llm.create(request)
            call_no += 1
            self._stores.cost.record(ref, call_no, resp.model, resp.usage)
            self._events.publish("cost.updated", ref.project_id, {"run_id": run.id})
            reason = self._stores.budget.exceeded(ref)
            if reason:
                self._stop_for_budget(run, ref, reason)
                return
            messages.append({"role": "assistant", "content": resp.content})
            uses = [b for b in resp.content if b.get("type") == "tool_use"]
            if resp.stop_reason != "tool_use" or not uses:
                text = "\n".join(b["text"] for b in resp.content if b.get("type") == "text")
                ok = resp.stop_reason == "end_turn"
                error = None if ok else f"stop: {resp.stop_reason}"
                self._stores.runs.finish(run.id, "succeeded" if ok else "failed", text, error)
                return
            results: list[dict[str, Any]] = []
            for use in uses:
                seq += 1
                results.append(self._tool_result(run, ctx, use, seq))
            messages.append({"role": "user", "content": results})
        self._stores.runs.finish(run.id, "failed", None, "max turns reached")

    def _stop_for_budget(self, run: Run, ref: CallRef, reason: str) -> None:
        if ref.ticket is not None:
            self._stores.inbox.hold(NewHold(ref.project_id, ref.feature, ref.ticket, "budget", reason))
        self._stores.runs.finish(run.id, "failed", None, f"budget: {reason}")

    def _tool_result(self, run: Run, ctx: ToolContext, use: dict[str, Any], seq: int) -> dict[str, Any]:
        outcome: ToolOutcome = self._tools.call(ctx, use["name"], use["input"])
        call = ToolCall(
            seq=seq,
            name=use["name"],
            target=outcome.target,
            status=outcome.status,
            summary=outcome.text[:200],
        )
        self._stores.runs.add_tool_call(run.id, call)
        return {
            "type": "tool_result",
            "tool_use_id": use["id"],
            "content": outcome.text,
            "is_error": outcome.status != "ok",
        }
