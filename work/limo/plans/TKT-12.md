---
ticket: TKT-12
feature: limo
scenarios: [SC-40, SC-41, SC-42]
scope: [ui, api]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/ui.feature, work/limo/reqs.md#REQ-39, work/limo/nfr.md#NFR-9#NFR-10, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, context/stack.md, context/glossary.md, context/adr/ADR-2.md, context/adr/ADR-13.md, engine/limo/app.py, engine/limo/config.py, engine/limo/agents/service.py, engine/limo/agents/models.py, engine/limo/agents/repo.py, engine/limo/agents/agent_service.py, engine/limo/api/agents_routes.py, engine/limo/api/runs_routes.py, engine/limo/incidents/service.py, engine/limo/incidents/repo.py:110-115, engine/limo/cost/repo.py, engine/limo/cost/pricing.py, engine/limo/common/constants.py, engine/limo/store/migrations/004_cost.sql, engine/limo/store/migrations/013_runs_interrupted.sql, engine/pyproject.toml, engine/tests/conftest.py, engine/tests/builders.py, engine/tests/fakes/llm.py, engine/tests/functional/test_cost.py:1-50, engine/tests/functional/test_incidents.py:60-100, mise.toml, scripts/fx.py (trace-check)]
---
# TKT-12: Live agent cards show model, state, ticket, cost and last run

## Design
- where: engine — new `limo/events/` (in-process event bus), new `limo/cards/` (card read model), `api/cards_routes.py`, `api/events.py` (SSE); `agents/service.py` and `incidents/service.py` publish events; `app.py` wiring; `tests/e2e_app.py` (engine with fakes for the UI e2e). UI — new `ui/` app (Vite + React + TS + Tailwind v4 + shadcn/ui components + react-query), agents page, theme toggle; `mise.toml` gains UI tasks.
- responsibilities:
  - `limo/events/bus.py` `EventBus` — thread-safe fan-out of `Event`s to subscriber queues; drops on a full queue
  - `limo/cards/repo.py` `CardRepo` — one SQL query: latest run per agent + its tokens, the agent's cost on that ticket, open-incident flag
  - `limo/cards/service.py` `AgentCardService` — one `AgentCard` per name in `AGENT_NAMES`, state rule, duration
  - `limo/api/cards_routes.py` — `GET /api/agent-cards`
  - `limo/api/events.py` — `GET /api/events` SSE stream (subscribe, `: connected`, events, `: ping` heartbeat, unsubscribe on disconnect)
  - `ui/src/api/events.ts` `useLiveEvents` — one EventSource; event type → invalidated react-query keys
  - `ui/src/pages/AgentsPage.tsx` — grid of `AgentCard`s from `GET /api/agent-cards`
  - `ui/src/components/AgentCard.tsx` — one card; `ThemeToggle.tsx` — light/dark switch (ADR-13)
- reuse: `AGENT_NAMES` (`common/constants.py`); `AgentSettingsRepo.all()` for models (as `agents/agent_service.py`); `format_usd` (`cost/pricing.py`); open-incident rule copied into SQL from `IncidentRepo.blocking_tickets` (`incidents/repo.py:110-115`); `connect` (`store/db.py`); test builders `add_cart_project`, `start_and_wait`, `wait_run`; fakes `FakeLlm`, `final_with`, `blocking_build`. Searched `limo/common/`, `limo/api/`, `ui/src/lib/` (none yet) for an event bus / SSE helper: none found.
- contracts:
  - `GET /api/agent-cards` → 200 `list[AgentCard]`, always 7 items in `AGENT_NAMES` order:
    `{"agent", "model", "state": "idle"|"active"|"stuck", "project": str|null, "feature": str|null, "ticket": str|null, "cost": "0.400000", "last_run": null | {"id", "status": RunStatus, "tokens": int, "started_at", "finished_at": str|null, "duration_s": int|null, "tries": int}}`
    - `model` = configured model (`agent_settings`, else `settings.default_model`)
    - `last_run` = the agent's latest run (any project) by `created_at`; `project/feature/ticket` from it; null when the agent never ran
    - `tokens` = sum of the 4 token kinds of that run; `tries` = run `attempt`; `duration_s` = int(finished_at − created_at) seconds, null while unfinished
    - `cost` = sum of `usage.cost_micros` of this agent on (project, feature, ticket) of that run, as `format_usd`; `"0.000000"` without a run
    - `state`: run `queued|running` → `active`; else agent ≠ `resolver` and (project, feature, ticket) has an incident with `status='open'` or (`status='needs_human'` and `reply IS NULL`) → `stuck`; else `idle`
  - `GET /api/events` → 200 `text/event-stream`, header `Cache-Control: no-cache`; first line `: connected`; each event `event: <type>\ndata: {"type", "at", "project_id", "payload"}\n\n`; `: ping` comment after `settings.sse_heartbeat_s` (default 15) without events
  - events published (type → payload):
    - `run.started` (RunService.start, after insert) → `{"run_id", "agent", "feature", "ticket"}`
    - `run.updated` (worker set status running) → same payload
    - `cost.updated` (after each usage record) → `{"run_id"}`
    - `run.finished` (worker done, any outcome; and per run failed by `fail_timed_out`) → same payload as run.started / `{"run_id"}` for timeouts
    - `incident.opened` (every incident row added) → `{"incident_id", "feature", "ticket", "trigger"}`
  - UI: query key `["agent-cards"]`; invalidated by `run.started`, `run.updated`, `run.finished`, `incident.opened`, `cost.updated`
- data: migration `014_runs_agent_index.sql`: `CREATE INDEX runs_agent_created ON runs (agent, created_at);` — no table changes
- decisions: follows ADR-2 (REST truth, SSE hints), ADR-13 (palette in `ui/src/styles/theme.css`, toggle in header, localStorage key `limo-theme`, axe contrast in e2e), ADR-5 (e2e engine = real app with fakes), ADR-8 (all UI commands are mise tasks). Pins TypeScript 5.9.3 (typescript-eslint 8.74 needs < 6.1; openapi-typescript needs ^5). No new ADR (libs are listed in stack.md / ADR-1 / ADR-13; `clsx`, `tailwind-merge`, `class-variance-authority` are shadcn/ui's own deps).

## Quality
### Security
- authn: n/a: ADR-7, engine and vite bind 127.0.0.1
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: no request input on both new endpoints (no params, no body)
- injection: card query is static parameterless SQL; React escapes rendered text; no `dangerouslySetInnerHTML`
- data exposure / PII: cards and events carry ids, agent names, counts, money only — no prompts, outputs, errors, tokens or keys
- secrets: none touched; `tests/e2e_app.py` uses `FakeLlm`/`FakeHost` and `_env_file=None`
- rate limit / abuse: subscriber queue max 1000 events, extra dropped (REST stays truth); stream ends on client disconnect
- audit: n/a: read-only views; runs/incidents already audited
### Performance
- queries (N+1, indexes): one query for all 7 cards (window function + correlated sums on indexed `usage_run`, `usage_project`); new index `runs_agent_created`
- pagination / limits: n/a: fixed 7 items
- payload size: ~2 KB cards; events < 300 B
- caching: none server-side; react-query cache invalidated by SSE (performance.md)
- external calls (timeouts/retries): none
- sync vs async: SSE generator is async and polls its queue every 0.1 s (no blocking get); publish is non-blocking `put_nowait` from worker threads
- NFR targets: NFR-9 (≤ 1 s) → FT-12.3 asserts `run.started` arrives < 1 s after POST; NFR-10 → FT-12.9 (both modes, axe `color-contrast`) + FT-12.10 (toggle in header, persisted)

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 list agent cards `GET /api/agent-cards` | FT-12.1 | n/a: no input | n/a: always all 7 agents | n/a: read only | n/a: read only | n/a: read only | FT-12.1, FT-12.2 | FT-12.4 |
| OP-2 event stream `GET /api/events` | FT-12.3, FT-12.4 | n/a: no input | n/a: single resource | n/a: read only | n/a: read only | n/a: read only | FT-12.5 | n/a: no external call |
| OP-3 agents page `ui/src/pages/AgentsPage.tsx` | FT-12.6, FT-12.7, FT-12.8 | n/a: no input | n/a: list view | n/a: read only | n/a: read only | n/a: read only | FT-12.9 | FT-12.11 |
| OP-4 theme toggle `ui/src/components/ThemeToggle.tsx` | FT-12.10 | n/a: two fixed modes | n/a: no target | n/a: local only | n/a: any state | FT-12.10 | n/a: two modes | n/a: no external call |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-12.1 | SC-40, OP-1:happy, OP-1:boundary | `engine/tests/functional/test_agent_cards.py` | `add_cart_project`; `PUT /api/agents/build/model` `{"model": "claude-haiku-5-5"}`; `PUT /api/prices/claude-haiku-5-5` `{"input": 4, "output": 20}`; `llm.script = [final_with(LlmUsage(40_000, 12_000))]`; `run = start_and_wait(client, "build")` | `GET /api/agent-cards` | 200; `[c["agent"] for c in body] == list(AGENT_NAMES)`; build card: `model == "claude-haiku-5-5"`, `state == "idle"`, `project == "shop"`, `feature == "cart"`, `ticket == "TKT-1"`, `cost == "0.400000"`, `last_run.id == run["id"]`, `last_run.status == "succeeded"`, `last_run.tokens == 52_000`, `last_run.tries == 1`, `last_run.started_at == run["created_at"]`, `last_run.finished_at == run["finished_at"]`, `last_run.duration_s == int((fromisoformat(finished_at) - fromisoformat(created_at)).total_seconds())`; plan card: `state == "idle"`, `ticket is None`, `cost == "0.000000"`, `last_run is None`, `model == "claude-opus-5-5"` |
| FT-12.2 | OP-1:boundary | same | as FT-12.1 but `llm.script` = two `final_with(LlmUsage(40_000, 12_000))`; `start_and_wait(client, "build")` twice (keep 2nd as `second`) | `GET /api/agent-cards` | build card `last_run.tries == 2`, `last_run.id == second["id"]`, `last_run.tokens == 52_000`, `cost == "0.800000"` |
| FT-12.3 | SC-41, OP-2:happy | same | `add_cart_project`; `llm.responder = blocking_build(settings.skills_dir, 1.0)`; open `client.stream("GET", "/api/events")`, `lines = r.iter_lines()`, `next(lines) == ": connected"`; `r.headers["content-type"].startswith("text/event-stream")` | `POST /api/projects/shop/runs` `{"agent": "build", "feature": "cart", "ticket": "TKT-1"}` (t0 = monotonic before POST) | `ev = next_event(lines, "run.started")`: `ev["type"] == "run.started"`, `ev["payload"]["agent"] == "build"`, `ev["payload"]["ticket"] == "TKT-1"`, `ev["project_id"]` is a non-empty str, `"at"` in ev; `monotonic() - t0 < 1.0`; `GET /api/agent-cards` build card `state == "active"`, `ticket == "TKT-1"`; then `next_event(lines, "run.finished")["payload"]["run_id"] == <POST id>` |
| FT-12.4 | SC-42, OP-1:external-failure, OP-2:happy | same | `add_cart_project`; `llm.fail_with = LlmError("overloaded")`; `failed = start_and_wait(client, "build")` (status `failed`); `llm.fail_with = None`; open the event stream as in FT-12.3 | `POST /api/projects/shop/features/cart/step` | step body `reason == "resolving"`; `ev = next_event(lines, "incident.opened")`: `ev["payload"]["ticket"] == "TKT-1"`, `ev["payload"]["trigger"] == "crash"`; `GET /api/agent-cards` build card `state == "stuck"`, `last_run.status == "failed"`; resolver card `state in ("active", "idle")` |
| FT-12.5 | OP-2:boundary | same | settings fixture has `sse_heartbeat_s=0.2`; open the event stream, `next(lines) == ": connected"` | no action | a line `": ping"` arrives within 2 s (loop over `lines` with a monotonic deadline) |
| FT-12.6 | SC-40, OP-3:happy | `ui/tests/AgentsPage.test.tsx` | `serveCards({ current: [card()] })` (harness: build, haiku, idle, TKT-1, cost `"0.400000"`, last run 52000 tokens, 240 s, finished `2026-11-26T14:05:00+00:00`, tries 1); `renderApp()` | card `agent-card-build` appears | text `claude-haiku-5-5`; fields (`data-field`): state `idle`, ticket `TKT-1`, cost `$0.40`, last run `52,000 tokens`, duration `4 min`, finished `2026-11-26 14:05 UTC`, tries `1` |
| FT-12.7 | SC-41, OP-3:happy | same | as FT-12.6 | `cards.current = [card({ state: "active" })]`; `FakeEventSource.last.emit("run.started")` | EventSource url `/api/events`; state field becomes `active` without re-render call; ticket `TKT-1` |
| FT-12.8 | SC-42, OP-3:happy | same | as FT-12.6 | `cards.current = [card({ state: "stuck" })]`; `emit("incident.opened")` | state field becomes `stuck` |
| FT-12.11 | OP-3:external-failure | same | `fetch` stub returns status 500 | `renderApp()` | text `Could not load agents.` appears |
| FT-12.9 | OP-3:boundary | `ui/e2e/agents.spec.ts` | engine `tests/e2e_app.py` (fakes, empty db) + vite on 5174 | open `/`; for mode light then dark: set `localStorage["limo-theme"]`, reload | all 7 `agent-card-<name>` visible; `<html>` has class `dark` only in dark mode; axe `color-contrast` violations `[]` in both modes |
| FT-12.10 | OP-4:happy, OP-4:idempotency | same | `page.emulateMedia({ colorScheme: "light" })`; open `/` | click button `Dark mode`; reload | `<html>` has class `dark` before and after reload; button `Light mode` visible |

## Context pack
- `engine/limo/common/constants.py` — add EVENT_TYPES
- `engine/limo/config.py` — add `sse_heartbeat_s`
- `engine/limo/agents/service.py` — publish run events
- `engine/limo/agents/models.py` — `RunStatus` (imported by cards models)
- `engine/limo/agents/settings_repo.py` — `AgentSettingsRepo.all()`
- `engine/limo/agents/agent_service.py` — imitate model lookup
- `engine/limo/incidents/service.py` — publish incident.opened
- `engine/limo/incidents/repo.py:110-115` — open-incident rule to mirror in SQL
- `engine/limo/cost/pricing.py` — `format_usd`
- `engine/limo/store/db.py` — `connect`
- `engine/limo/store/migrations/004_cost.sql` — usage column names
- `engine/limo/store/migrations/013_runs_interrupted.sql` — runs columns
- `engine/limo/projects/repo.py` — repo pattern to imitate
- `engine/limo/api/agents_routes.py` — router pattern to imitate
- `engine/limo/app.py` — wiring
- `engine/pyproject.toml` — import-linter source modules
- `engine/tests/conftest.py` — fixtures (`settings`, `client`, `llm`)
- `engine/tests/builders.py` — add `next_event`; existing `add_cart_project`, `start_and_wait`, `wait_run`
- `engine/tests/fakes/llm.py` — `FakeLlm`, `final_with`, `blocking_build`
- `engine/tests/fakes/host.py:1-40` — `FakeHost()` constructor
- `engine/tests/functional/test_cost.py:1-50` — test style to imitate
- `mise.toml` — tasks

## Steps
### STEP-1 Event type constants
- file: `engine/limo/common/constants.py` (edit)
- do: append
```python
EVENT_TYPES: tuple[str, ...] = (
    "run.started",
    "run.updated",
    "run.finished",
    "ticket.changed",
    "incident.opened",
    "cost.updated",
    "prompt.saved",
)
```
- verify: `cd engine && uv run python -c "from limo.common.constants import EVENT_TYPES; print(len(EVENT_TYPES))"` → `7`

### STEP-2 Event bus
- file: `engine/limo/events/__init__.py` (create, empty) and `engine/limo/events/bus.py` (create)
- do:
```python
import json
import queue
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime

from limo.common.constants import EVENT_TYPES

MAX_QUEUED = 1000


@dataclass(frozen=True)
class Event:
    type: str
    at: str
    project_id: str | None
    payload: dict[str, object]

    def to_sse(self) -> str:
        data = {"type": self.type, "at": self.at, "project_id": self.project_id, "payload": self.payload}
        return f"event: {self.type}\ndata: {json.dumps(data)}\n\n"


class EventBus:
    """In-process fan-out of change events to SSE subscribers; publish is safe from any thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[Event]] = []

    def subscribe(self) -> queue.Queue[Event]:
        sub: queue.Queue[Event] = queue.Queue(maxsize=MAX_QUEUED)
        with self._lock:
            self._subscribers.append(sub)
        return sub

    def unsubscribe(self, sub: queue.Queue[Event]) -> None:
        with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    def publish(self, event_type: str, project_id: str | None, payload: dict[str, object]) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {event_type}")
        event = Event(event_type, datetime.now(UTC).isoformat(), project_id, payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            with suppress(queue.Full):  # slow client drops hints; REST stays the truth (ADR-2)
                sub.put_nowait(event)
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-3 Heartbeat setting
- file: `engine/limo/config.py` (edit)
- do: add field `sse_heartbeat_s: float = 15.0` after `host_timeout_s`
- verify: `cd engine && uv run python -c "from limo.config import Settings; print(Settings(_env_file=None).sse_heartbeat_s)"` → `15.0`

### STEP-4 SSE test helper
- file: `engine/tests/builders.py` (edit)
- do: add (import `json` and `Iterator` from `collections.abc` if missing)
```python
def next_event(lines: Iterator[str], event_type: str, timeout_s: float = 5.0) -> dict[str, Any]:
    """Read SSE lines until an event of `event_type`; return its parsed data envelope.
    Needs a heartbeat shorter than `timeout_s` so the loop wakes up."""
    deadline = time.monotonic() + timeout_s
    current: str | None = None
    for line in lines:
        if time.monotonic() > deadline:
            break
        if line.startswith("event: "):
            current = line.removeprefix("event: ")
        elif line.startswith("data: ") and current == event_type:
            return dict(json.loads(line.removeprefix("data: ")))
    raise AssertionError(f"no {event_type} event within {timeout_s} s")
```
- verify: `cd engine && uv run ruff check tests/builders.py` → no errors

### STEP-5 Engine functional tests
- file: `engine/tests/functional/test_agent_cards.py` (create)
- do: write FT-12.1 … FT-12.5 exactly as in the Functional tests table. Names: `test_ft_12_1_card_shows_model_state_ticket_cost_last_run`, `test_ft_12_2_card_counts_tries_and_sums_ticket_cost`, `test_ft_12_3_run_start_turns_card_active_live`, `test_ft_12_4_open_incident_turns_card_stuck_live`, `test_ft_12_5_idle_stream_sends_heartbeat`; each docstring starts `"""FT-12.<k> …`. Override the conftest `settings` fixture in this module so every test has a short heartbeat:
```python
@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", sse_heartbeat_s=0.2, _env_file=None
    )
```
  Imports: `AGENT_NAMES` from `limo.common.constants`, `LlmError`, `LlmUsage` from `limo.llm.ports`, `add_cart_project`, `next_event`, `start_and_wait`, `wait_run` from `tests.builders`, `FakeLlm`, `blocking_build`, `final_with` from `tests.fakes.llm`. Helper in the module: `def _card(client: TestClient, agent: str) -> dict[str, Any]` = the item of `client.get("/api/agent-cards").json()` with that agent. Event stream pattern:
```python
with client.stream("GET", "/api/events") as r:
    lines = r.iter_lines()
    assert next(lines) == ": connected"
    ...  # act, then next_event(lines, "<type>") inside the with-block
```
  FT-12.3: after asserting run.started and the active card, call `wait_run(client, run_id)` before `next_event(lines, "run.finished")`.
- verify: `mise run test:engine -- -k ft_12` → `FAIL: 404` on `/api/agent-cards` and `/api/events`

### STEP-6 Index migration
- file: `engine/limo/store/migrations/014_runs_agent_index.sql` (create)
- do: `CREATE INDEX runs_agent_created ON runs (agent, created_at);`
- verify: `mise run test:engine -- -k ft_1_` → passes (migrations apply)

### STEP-7 Card models
- file: `engine/limo/cards/__init__.py` (create, empty) and `engine/limo/cards/models.py` (create)
- do:
```python
from typing import Literal

from pydantic import BaseModel

from limo.agents.models import RunStatus

AgentState = Literal["idle", "active", "stuck"]


class LastRun(BaseModel):
    id: str
    status: RunStatus
    tokens: int
    started_at: str
    finished_at: str | None
    duration_s: int | None
    tries: int


class AgentCard(BaseModel):
    agent: str
    model: str
    state: AgentState
    project: str | None
    feature: str | None
    ticket: str | None
    cost: str
    last_run: LastRun | None
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-8 Card repo
- file: `engine/limo/cards/repo.py` (create)
- like: `engine/limo/projects/repo.py`
- do: frozen dataclass `CardRow(agent: str, run_id: str, project: str, feature: str, ticket: str | None, status: RunStatus, attempt: int, created_at: str, finished_at: str | None, tokens: int, cost_micros: int, has_incident: bool)`; class `CardRepo(db_path: Path)` with `latest_runs(self) -> list[CardRow]` running exactly this SQL (open-incident rule mirrors `IncidentRepo.blocking_tickets`):
```sql
SELECT r.agent, r.id AS run_id, p.name AS project, r.feature, r.ticket, r.status, r.attempt,
  r.created_at, r.finished_at,
  (SELECT COALESCE(SUM(u.input_tokens + u.output_tokens + u.cache_read_tokens + u.cache_write_tokens), 0)
     FROM usage u WHERE u.run_id = r.id) AS tokens,
  (SELECT COALESCE(SUM(u.cost_micros), 0) FROM usage u
     WHERE u.project_id = r.project_id AND u.feature = r.feature AND u.ticket IS r.ticket
       AND u.agent = r.agent) AS cost_micros,
  EXISTS (SELECT 1 FROM incidents i
     WHERE i.project_id = r.project_id AND i.feature = r.feature AND i.ticket = r.ticket
       AND (i.status = 'open' OR (i.status = 'needs_human' AND i.reply IS NULL))) AS has_incident
FROM (SELECT runs.*, ROW_NUMBER() OVER (PARTITION BY agent ORDER BY created_at DESC, rowid DESC) AS rn
      FROM runs) r
JOIN projects p ON p.id = r.project_id
WHERE r.rn = 1
```
  Map each row with `CardRow(**{**dict(row), "has_incident": bool(row["has_incident"])})`.
- verify: `cd engine && uv run mypy` → `Success`

### STEP-9 Card service
- file: `engine/limo/cards/service.py` (create)
- do: class `AgentCardService(repo: CardRepo, settings: AgentSettingsRepo, default_model: str)`; `list(self) -> list[AgentCard]`: `rows = {r.agent: r for r in self._repo.latest_runs()}`, `models = self._settings.all()`, return `[_card(name, models.get(name, self._default_model), rows.get(name)) for name in AGENT_NAMES]`. Module functions:
  - `_card(agent: str, model: str, row: CardRow | None) -> AgentCard` — no row → `state="idle"`, project/feature/ticket/last_run `None`, `cost=format_usd(0)`; else fields per Design contracts, `cost=format_usd(row.cost_micros)`, `last_run=LastRun(id=row.run_id, status=row.status, tokens=row.tokens, started_at=row.created_at, finished_at=row.finished_at, duration_s=_duration(row), tries=row.attempt)`
  - `_state(row: CardRow) -> AgentState` — `"active"` if `row.status in ("queued", "running")`; `"stuck"` if `row.has_incident and row.agent != "resolver"`; else `"idle"`
  - `_duration(row: CardRow) -> int | None` — `None` if `row.finished_at is None`; else `int((datetime.fromisoformat(row.finished_at) - datetime.fromisoformat(row.created_at)).total_seconds())`
- verify: `cd engine && uv run mypy` → `Success`

### STEP-10 Cards route
- file: `engine/limo/api/cards_routes.py` (create)
- like: `engine/limo/api/agents_routes.py`
- do: `def cards_router(service: AgentCardService) -> APIRouter` with `@router.get("/api/agent-cards", response_model=list[AgentCard]) def list_agent_cards() -> list[AgentCard]: return service.list()`
- verify: `cd engine && uv run mypy` → `Success`

### STEP-11 SSE route
- file: `engine/limo/api/events.py` (create)
- do:
```python
import asyncio
import queue
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from limo.events.bus import EventBus

POLL_S = 0.1


def events_router(bus: EventBus, heartbeat_s: float) -> APIRouter:
    router = APIRouter()

    @router.get("/api/events")
    async def stream_events(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _stream(bus, request, heartbeat_s),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return router


async def _stream(bus: EventBus, request: Request, heartbeat_s: float) -> AsyncIterator[str]:
    sub = bus.subscribe()
    try:
        yield ": connected\n\n"
        idle = 0.0
        while not await request.is_disconnected():
            try:
                event = sub.get_nowait()
            except queue.Empty:
                await asyncio.sleep(POLL_S)
                idle += POLL_S
                if idle >= heartbeat_s:
                    idle = 0.0
                    yield ": ping\n\n"
                continue
            idle = 0.0
            yield event.to_sse()
    finally:
        bus.unsubscribe(sub)
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-12 RunService publishes run events
- file: `engine/limo/agents/service.py` (edit)
- do:
  - import `EventBus` from `limo.events.bus`; constructor becomes `__init__(self, stores: RunStores, llm: LlmClient, tools: ToolBox, config: RunConfig, events: EventBus)`, store `self._events = events`
  - module function `_payload(run: Run) -> dict[str, object]` → `{"run_id": run.id, "agent": run.agent, "feature": run.feature, "ticket": run.ticket}`
  - `start`: after `self._stores.runs.insert(run, project.id)` add `self._events.publish("run.started", project.id, _payload(run))`; then `self._pool.submit(self._execute, run, project.id)`
  - replace `_execute` with:
```python
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
```
  - `_loop`: right after `self._stores.cost.record(ref, call_no, resp.model, resp.usage)` add `self._events.publish("cost.updated", ref.project_id, {"run_id": run.id})`
  - `fail_timed_out`: inside the loop after `finish(...)` add `self._events.publish("run.finished", project_id, {"run_id": run_id})`
- verify: `cd engine && uv run mypy` → only error: `app.py` missing argument `events` (fixed in STEP-14)

### STEP-13 IncidentService publishes incident.opened
- file: `engine/limo/incidents/service.py` (edit)
- do: import `EventBus` from `limo.events.bus`; add last field `events: EventBus` to `IncidentDeps`; in `__init__` `self._events = deps.events`; add method
```python
    def _record(self, project: Project, feature: str, row: IncidentRow) -> None:
        self._repo.add(project.id, feature, row)
        payload: dict[str, object] = {
            "incident_id": row.id, "feature": feature, "ticket": row.ticket, "trigger": row.trigger
        }
        self._events.publish("incident.opened", project.id, payload)
```
  and replace both `self._repo.add(project.id, feature, row)` calls (in `_follow_up` and `_open`) with `self._record(project, feature, row)`
- verify: `cd engine && uv run mypy` → only errors in `app.py` (fixed in STEP-14)

### STEP-14 Wiring
- file: `engine/limo/app.py` (edit)
- do: import `EventBus` (`limo.events.bus`), `AgentCardService` (`limo.cards.service`), `CardRepo` (`limo.cards.repo`), `cards_router` (`limo.api.cards_routes`), `events_router` (`limo.api.events`). In `create_app` after `migrate`/recovery: `events = EventBus()`. Pass `events` as 5th argument of `RunService(...)` and as `events=events` (last) in `IncidentDeps(...)`. After the agents router: `app.include_router(cards_router(AgentCardService(CardRepo(settings.db_path), agent_settings, settings.default_model)))` and `app.include_router(events_router(events, settings.sse_heartbeat_s))`.
- verify: `mise run test:engine -- -k ft_12` → 5 passed

### STEP-15 Import contracts
- file: `engine/pyproject.toml` (edit)
- do: in the contract "Services use ports, not adapters (ADR-4)" add `"limo.cards"`, `"limo.events"` to `source_modules`
- verify: `mise run arch` → contracts kept

### STEP-16 E2E engine with fakes
- file: `engine/tests/e2e_app.py` (create)
- do:
```python
"""Engine for the UI e2e tests: the real app on 127.0.0.1:8701 with fake Claude API and fake repo host.
`python -m tests.e2e_app --openapi` prints the OpenAPI document instead (used by `mise run gen:api`)."""

import json
import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm

PORT = 8701


def build_app() -> FastAPI:
    settings = Settings(data_dir=Path(tempfile.mkdtemp(prefix="limo-e2e-")), _env_file=None)
    deps = Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=FakeLlm(), host=FakeHost())
    return create_app(settings, deps)


def main() -> None:
    app = build_app()
    if "--openapi" in sys.argv:
        print(json.dumps(app.openapi(), indent=2))
        return
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
```
- verify: `cd engine && uv run python -m tests.e2e_app --openapi | grep -c '"AgentCard"'` → ≥ 1

### STEP-17 mise tasks for the UI
- file: `mise.toml` (edit)
- do: replace every task after `[tools]` with exactly:
```toml
[tasks.setup]
description = "Install engine and UI dependencies (and the e2e browser)"
run = ["cd engine && uv sync", "cd ui && npm ci", "cd ui && npx playwright install chromium"]

[tasks."up:engine"]
description = "Start the engine on 127.0.0.1:8700"
dir = "engine"
run = "uv run uvicorn limo.app:app_from_env --factory --host 127.0.0.1 --port 8700"

[tasks."up:ui"]
description = "Start the UI dev server on 127.0.0.1:5173 (proxies /api to the engine)"
dir = "ui"
run = "npx vite"

[tasks.up]
description = "Start engine and UI"
depends = ["up:engine", "up:ui"]

[tasks."gen:api"]
description = "Regenerate UI API types from the engine OpenAPI document"
run = [
  "cd engine && uv run python -m tests.e2e_app --openapi > ../ui/openapi.json",
  "cd ui && npx openapi-typescript openapi.json -o src/api/schema.d.ts",
]

[tasks."test:engine"]
description = "Run engine tests; pass pytest args after --"
dir = "engine"
run = "uv run pytest"

[tasks."test:ui"]
description = "Run UI component tests (Vitest); pass vitest args after --"
dir = "ui"
run = "npx vitest run"

[tasks."test:e2e"]
description = "Run UI e2e tests (Playwright) against the engine with fakes"
dir = "ui"
run = "npx playwright test"

[tasks.test]
description = "Run all test suites"
depends = ["test:engine", "test:ui", "test:e2e"]

[tasks.lint]
description = "Lint and format check (ruff; eslint + prettier)"
run = [
  "cd engine && uv run ruff check .",
  "cd engine && uv run ruff format --check .",
  "cd ui && npx eslint .",
  "cd ui && npx prettier --check .",
]

[tasks.fmt]
description = "Auto-format and auto-fix (ruff; prettier)"
run = ["cd engine && uv run ruff check --fix .", "cd engine && uv run ruff format .", "cd ui && npx prettier --write ."]

[tasks.types]
description = "Type check (mypy --strict; tsc --noEmit)"
run = ["cd engine && uv run mypy", "cd ui && npx tsc --noEmit"]

[tasks.arch]
description = "Architecture import contracts (import-linter)"
dir = "engine"
run = "uv run lint-imports"

[tasks.dup]
description = "Duplicate code check (jscpd)"
dir = "engine"
run = "npx --yes jscpd@4.0.5 --threshold 0 --min-lines 10 --gitignore --ignore '**/schema.d.ts,**/components/ui/**' limo ../ui/src"

[tasks.gates]
description = "All quality gates"
depends = ["lint", "types", "arch", "dup"]
```
- verify: `mise tasks` → lists `test:ui`, `test:e2e`, `gen:api`, `up:ui`

### STEP-18 UI package and dependencies
- file: `ui/package.json` (create), `ui/package-lock.json` (generated)
- do: create `ui/package.json`:
```json
{
  "name": "limo-ui",
  "private": true,
  "version": "0.0.0",
  "type": "module"
}
```
  then from `ui/` run (exact versions; TypeScript stays 5.9.3, see Design decisions):
  `mise exec -- npm i --save-exact react@19.3.1 react-dom@19.3.1 @tanstack/react-query@5.108.4 class-variance-authority@0.7.1 clsx@2.1.1 tailwind-merge@3.7.1`
  `mise exec -- npm i --save-exact -D vite@8.4.0 @vitejs/plugin-react@6.3.0 typescript@5.9.3 tailwindcss@4.3.5 @tailwindcss/vite@4.3.5 vitest@5.1.2 jsdom@31.0.1 @testing-library/react@16.3.3 @testing-library/jest-dom@8.0.0 @playwright/test@1.65.1 @axe-core/playwright@4.14.1 eslint@10.15.0 typescript-eslint@8.74.0 eslint-plugin-react-hooks@7.1.1 @eslint/js@10.0.1 globals@17.14.0 prettier@3.10.1 openapi-typescript@7.13.0 @types/react@19.3.3 @types/react-dom@19.3.0 @types/node@22.20.7`
  `mise exec -- npx playwright install chromium`
- verify: `cd ui && npm ls --depth=0` → no `ERR!`/`missing`

### STEP-19 UI config files
- file: `ui/index.html`, `ui/vite.config.ts`, `ui/tsconfig.json`, `ui/eslint.config.js`, `ui/.prettierrc.json`, `ui/.prettierignore`, `ui/.gitignore` (create)
- do: exact contents —
  `ui/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Limo</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```
  `ui/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const apiUrl = process.env.LIMO_API_URL ?? "http://127.0.0.1:8700";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": apiUrl } },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.tsx"],
    setupFiles: ["tests/setup.ts"],
  },
});
```
  `ui/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "types": ["node", "vite/client", "@testing-library/jest-dom/vitest"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src", "tests", "e2e", "vite.config.ts", "playwright.config.ts"]
}
```
  `ui/eslint.config.js` (size/complexity rules mirror code-rules.md):
```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "playwright-report", "test-results", "src/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      complexity: ["error", 10],
      "max-lines": ["error", 300],
      "max-lines-per-function": ["error", 40],
      "max-params": ["error", 5],
    },
  },
);
```
  `ui/.prettierrc.json`: `{ "printWidth": 110 }`
  `ui/.prettierignore` (one per line): `dist`, `playwright-report`, `test-results`, `package-lock.json`, `openapi.json`, `src/api/schema.d.ts`
  `ui/.gitignore` (one per line): `dist`, `playwright-report`, `test-results`, `openapi.json`
- verify: `cd ui && npx tsc --noEmit` → error only `No inputs were found` or none (no src yet)

### STEP-20 Generated API types
- file: `ui/src/api/schema.d.ts` (generated)
- do: `mise run gen:api`
- verify: `grep -c "AgentCard" ui/src/api/schema.d.ts` → ≥ 1 and `grep -c "LastRun" ui/src/api/schema.d.ts` → ≥ 1

### STEP-21 Theme and lib helpers
- file: `ui/src/styles/theme.css`, `ui/src/lib/utils.ts`, `ui/src/lib/format.ts`, `ui/src/lib/theme.ts` (create)
- do: `ui/src/styles/theme.css` (the palette, ADR-13; components use only these tokens):
```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

/* Limo palette (ADR-13): slate neutrals with a teal accent. Components use these tokens only. */
:root {
  --background: oklch(0.985 0.002 247);
  --foreground: oklch(0.21 0.03 265);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.21 0.03 265);
  --muted: oklch(0.95 0.005 247);
  --muted-foreground: oklch(0.45 0.03 257);
  --border: oklch(0.9 0.01 255);
  --primary: oklch(0.45 0.09 185);
  --primary-foreground: oklch(0.985 0.002 247);
  --secondary: oklch(0.93 0.01 255);
  --secondary-foreground: oklch(0.21 0.03 265);
  --destructive: oklch(0.5 0.19 27);
  --destructive-foreground: oklch(0.985 0.002 247);
  --ring: oklch(0.45 0.09 185);
  --radius: 0.625rem;
}

.dark {
  --background: oklch(0.17 0.02 265);
  --foreground: oklch(0.96 0.005 247);
  --card: oklch(0.22 0.025 265);
  --card-foreground: oklch(0.96 0.005 247);
  --muted: oklch(0.28 0.025 265);
  --muted-foreground: oklch(0.75 0.02 257);
  --border: oklch(0.32 0.025 265);
  --primary: oklch(0.78 0.11 185);
  --primary-foreground: oklch(0.2 0.03 265);
  --secondary: oklch(0.32 0.025 265);
  --secondary-foreground: oklch(0.96 0.005 247);
  --destructive: oklch(0.7 0.17 25);
  --destructive-foreground: oklch(0.2 0.03 265);
  --ring: oklch(0.78 0.11 185);
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-border: var(--border);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-destructive: var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-ring: var(--ring);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
}

body {
  background-color: var(--background);
  color: var(--foreground);
}
```
  `ui/src/lib/utils.ts`:
```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```
  `ui/src/lib/format.ts`:
```ts
/** "0.400000" → "$0.40" (API money is a 6-place decimal string). */
export function formatUsd(amount: string): string {
  return `$${Number(amount).toFixed(2)}`;
}

/** 52000 → "52,000 tokens". */
export function formatTokens(tokens: number): string {
  return `${tokens.toLocaleString("en-US")} tokens`;
}

/** 240 → "4 min", 45 → "45 s", null → "running". */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "running";
  if (seconds < 60) return `${seconds} s`;
  return `${Math.round(seconds / 60)} min`;
}

/** ISO-8601 UTC → "2026-11-26 14:05 UTC"; null → "—". */
export function formatTime(iso: string | null): string {
  if (iso === null) return "—";
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}
```
  `ui/src/lib/theme.ts`:
```ts
export type Theme = "light" | "dark";

const KEY = "limo-theme";

/** Stored choice, else the system preference (ADR-13). */
export function initialTheme(): Theme {
  const stored = localStorage.getItem(KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Sets the `dark` class on <html> and remembers the choice. */
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem(KEY, theme);
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-22 API client, types, live events
- file: `ui/src/api/client.ts`, `ui/src/api/types.ts`, `ui/src/api/events.ts` (create)
- do:
  `ui/src/api/client.ts`:
```ts
/** GET a JSON resource from the engine; throws on a non-2xx status. */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`GET ${path} failed: ${response.status}`);
  return (await response.json()) as T;
}
```
  `ui/src/api/types.ts`:
```ts
import type { components } from "./schema";

export type AgentCard = components["schemas"]["AgentCard"];
export type LastRun = components["schemas"]["LastRun"];
```
  `ui/src/api/events.ts`:
```ts
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

/** SSE event type → REST queries it invalidates (api.md › SSE events; REST stays the truth). */
export const INVALIDATES: Record<string, QueryKey[]> = {
  "run.started": [["agent-cards"]],
  "run.updated": [["agent-cards"]],
  "run.finished": [["agent-cards"]],
  "incident.opened": [["agent-cards"]],
  "cost.updated": [["agent-cards"]],
};

/** Opens one EventSource on /api/events and refetches the matching queries on each event. */
export function useLiveEvents(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/events");
    for (const [type, keys] of Object.entries(INVALIDATES)) {
      source.addEventListener(type, () => {
        for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
      });
    }
    return () => source.close();
  }, [queryClient]);
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-23 shadcn/ui components
- file: `ui/src/components/ui/card.tsx`, `ui/src/components/ui/badge.tsx`, `ui/src/components/ui/button.tsx` (create; shadcn/ui sources, tokens only)
- do: `card.tsx`:
```tsx
import * as React from "react";

import { cn } from "@/lib/utils";

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "bg-card text-card-foreground flex flex-col gap-4 rounded-xl border border-border py-5 shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex items-start justify-between gap-2 px-5", className)}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-title" className={cn("leading-none font-semibold", className)} {...props} />;
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-description" className={cn("text-muted-foreground text-sm", className)} {...props} />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("px-5", className)} {...props} />;
}

export { Card, CardContent, CardDescription, CardHeader, CardTitle };
```
  `badge.tsx`:
```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        outline: "border-border text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge };
```
  `button.tsx`:
```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        outline: "border border-border bg-background text-foreground hover:bg-muted",
        ghost: "text-foreground hover:bg-muted",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

function Button({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return (
    <button data-slot="button" className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}

export { Button };
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-24 Vitest harness and component tests
- file: `ui/tests/setup.ts`, `ui/tests/harness.tsx`, `ui/tests/AgentsPage.test.tsx` (create)
- do: `ui/tests/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```
  `ui/tests/harness.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";

import type { AgentCard } from "@/api/types";
import { App } from "@/App";

/** Stand-in for the browser EventSource; `emit` delivers one SSE event to listeners. */
export class FakeEventSource {
  static last: FakeEventSource | null = null;
  readonly url: string;
  private listeners = new Map<string, Array<() => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  addEventListener(type: string, listener: () => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {}

  emit(type: string): void {
    for (const listener of this.listeners.get(type) ?? []) listener();
  }
}

/** Engine stub: GET /api/agent-cards answers with whatever `cards.current` holds at call time. */
export function serveCards(cards: { current: AgentCard[] }, status = 200): void {
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(cards.current), { status })),
  );
}

/** Renders the whole app with a fresh query client (no retries). */
export function renderApp(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

export function card(overrides: Partial<AgentCard> = {}): AgentCard {
  return {
    agent: "build",
    model: "claude-haiku-5-5",
    state: "idle",
    project: "shop",
    feature: "cart",
    ticket: "TKT-1",
    cost: "0.400000",
    last_run: {
      id: "r1",
      status: "succeeded",
      tokens: 52000,
      started_at: "2026-11-26T14:01:00+00:00",
      finished_at: "2026-11-26T14:05:00+00:00",
      duration_s: 240,
      tries: 1,
    },
    ...overrides,
  };
}
```
  `ui/tests/AgentsPage.test.tsx`:
```tsx
import { act, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { card, FakeEventSource, renderApp, serveCards } from "./harness";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

function field(agent: string, name: string): string {
  const el = within(screen.getByTestId(`agent-card-${agent}`)).getByText(
    (_, node) => node?.getAttribute("data-field") === name,
  );
  return el.textContent ?? "";
}

test("FT-12.6 card shows model, state, ticket, cost and last run", async () => {
  serveCards({ current: [card()] });
  renderApp();
  await screen.findByTestId("agent-card-build");
  expect(screen.getByText("claude-haiku-5-5")).toBeInTheDocument();
  expect(field("build", "state")).toBe("idle");
  expect(field("build", "ticket")).toBe("TKT-1");
  expect(field("build", "cost")).toBe("$0.40");
  expect(field("build", "last run")).toBe("52,000 tokens");
  expect(field("build", "duration")).toBe("4 min");
  expect(field("build", "finished")).toBe("2026-11-26 14:05 UTC");
  expect(field("build", "tries")).toBe("1");
});

test("FT-12.7 run.started event turns the card active without reload", async () => {
  const cards = { current: [card()] };
  serveCards(cards);
  renderApp();
  await screen.findByTestId("agent-card-build");
  expect(FakeEventSource.last?.url).toBe("/api/events");
  cards.current = [card({ state: "active" })];
  act(() => FakeEventSource.last?.emit("run.started"));
  await vi.waitFor(() => expect(field("build", "state")).toBe("active"));
  expect(field("build", "ticket")).toBe("TKT-1");
});

test("FT-12.8 incident.opened event turns the card stuck without reload", async () => {
  const cards = { current: [card({ last_run: { ...card().last_run!, status: "failed" } })] };
  serveCards(cards);
  renderApp();
  await screen.findByTestId("agent-card-build");
  cards.current = [card({ state: "stuck" })];
  act(() => FakeEventSource.last?.emit("incident.opened"));
  await vi.waitFor(() => expect(field("build", "state")).toBe("stuck"));
});

test("FT-12.11 engine error shows a load error", async () => {
  serveCards({ current: [] }, 500);
  renderApp();
  expect(await screen.findByText("Could not load agents.")).toBeInTheDocument();
});
```
- verify: `mise run test:ui` → `FAIL: Failed to resolve import "@/App"`

### STEP-25 Agent card, theme toggle, page, app shell
- file: `ui/src/components/AgentCard.tsx`, `ui/src/components/ThemeToggle.tsx`, `ui/src/pages/AgentsPage.tsx`, `ui/src/App.tsx`, `ui/src/main.tsx` (create)
- do: `ui/src/components/AgentCard.tsx`:
```tsx
import type { AgentCard as AgentCardData } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDuration, formatTime, formatTokens, formatUsd } from "@/lib/format";

const STATE_VARIANT = { idle: "secondary", active: "default", stuck: "destructive" } as const;

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd data-field={label}>{value}</dd>
    </div>
  );
}

/** One agent: model, state, current ticket, its cost on that ticket, and its last run (REQ-39). */
export function AgentCard({ card }: { card: AgentCardData }) {
  const run = card.last_run;
  return (
    <Card data-testid={`agent-card-${card.agent}`} aria-label={`agent ${card.agent}`}>
      <CardHeader>
        <div className="flex flex-col gap-1">
          <CardTitle>{card.agent}</CardTitle>
          <CardDescription>{card.model}</CardDescription>
        </div>
        <Badge variant={STATE_VARIANT[card.state]} data-field="state">
          {card.state}
        </Badge>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col gap-1">
          <Field label="ticket" value={card.ticket ?? "—"} />
          <Field label="cost" value={formatUsd(card.cost)} />
          <Field label="last run" value={run ? formatTokens(run.tokens) : "—"} />
          <Field label="duration" value={run ? formatDuration(run.duration_s) : "—"} />
          <Field label="finished" value={run ? formatTime(run.finished_at) : "—"} />
          <Field label="tries" value={run ? String(run.tries) : "—"} />
        </dl>
      </CardContent>
    </Card>
  );
}
```
  `ui/src/components/ThemeToggle.tsx`:
```tsx
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { applyTheme, initialTheme, type Theme } from "@/lib/theme";

/** Header switch between light and dark; starts from the stored or system mode (ADR-13). */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    const start = initialTheme();
    applyTheme(start);
    return start;
  });
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
    >
      {next === "dark" ? "Dark mode" : "Light mode"}
    </Button>
  );
}
```
  `ui/src/pages/AgentsPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import type { AgentCard as AgentCardData } from "@/api/types";
import { AgentCard } from "@/components/AgentCard";

/** Grid of live agent cards; SSE events refetch `agent-cards` (see api/events.ts). */
export function AgentsPage() {
  const cards = useQuery({
    queryKey: ["agent-cards"],
    queryFn: () => getJson<AgentCardData[]>("/api/agent-cards"),
  });
  if (cards.isPending) return <p className="text-muted-foreground">Loading agents…</p>;
  if (cards.isError) return <p className="text-destructive">Could not load agents.</p>;
  return (
    <section aria-label="agents" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.data.map((card) => (
        <AgentCard key={card.agent} card={card} />
      ))}
    </section>
  );
}
```
  `ui/src/App.tsx`:
```tsx
import { useLiveEvents } from "@/api/events";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AgentsPage } from "@/pages/AgentsPage";

export function App() {
  useLiveEvents();
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <h1 className="text-lg font-semibold">Limo</h1>
        <ThemeToggle />
      </header>
      <main className="p-6">
        <AgentsPage />
      </main>
    </div>
  );
}
```
  `ui/src/main.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import "@/styles/theme.css";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
```
- verify: `mise run test:ui` → 4 passed

### STEP-26 Playwright e2e
- file: `ui/playwright.config.ts`, `ui/e2e/agents.spec.ts` (create)
- do: `ui/playwright.config.ts`:
```ts
import { defineConfig, devices } from "@playwright/test";

/** E2E: the real UI (vite) against the engine started with fakes (engine/tests/e2e_app.py). */
export default defineConfig({
  testDir: "e2e",
  use: { baseURL: "http://127.0.0.1:5174" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run python -m tests.e2e_app",
      cwd: "../engine",
      url: "http://127.0.0.1:8701/api/agent-cards",
      reuseExistingServer: false,
    },
    {
      command: "npx vite --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      env: { LIMO_API_URL: "http://127.0.0.1:8701" },
      reuseExistingServer: false,
    },
  ],
});
```
  `ui/e2e/agents.spec.ts`:
```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const AGENTS = ["architecture", "spec", "plan", "build", "verify", "close", "resolver"];

test("FT-12.9 agents page shows every agent card in light and dark with AA contrast", async ({ page }) => {
  await page.goto("/");
  for (const agent of AGENTS) await expect(page.getByTestId(`agent-card-${agent}`)).toBeVisible();
  for (const mode of ["light", "dark"]) {
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await expect(page.getByTestId("agent-card-build")).toBeVisible();
    await expect(page.locator("html")).toHaveClass(mode === "dark" ? /dark/ : /^(?!.*dark)/);
    const scan = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
    expect(scan.violations).toEqual([]);
  }
});

test("FT-12.10 theme toggle switches mode and the choice survives a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Light mode" })).toBeVisible();
});
```
- verify: `mise run test:e2e` → 2 passed

### STEP-27 Format and full gates
- file: none (format only)
- do: `mise run fmt`
- verify: `mise run gates` → all pass; `mise run test` → all suites pass

## Do not
- edit `scripts/fx.py`, existing migrations, or existing tests' meaning
- add npm packages beyond STEP-18, or Python packages
- hard-code colors in components (only theme tokens, ADR-13)
- send commands over SSE or put run output, errors, or prompts into event payloads
- add a `scripts` section to `ui/package.json` (mise tasks are the interface, ADR-8)

## Doc updates
- context/api.md: Reference implementations — add `- agent cards: engine/limo/api/cards_routes.py (GET /api/agent-cards → 7 cards in AGENT_NAMES order; state idle|active|stuck)`; replace `- SSE: (planned) engine/limo/api/events.py` with `- SSE: engine/limo/api/events.py (GET /api/events; first line ": connected", ": ping" every sse_heartbeat_s; published now: run.started, run.updated, run.finished, cost.updated, incident.opened — via limo/events/bus.py EventBus)`
- context/data.md: Migrations/entities — add `- runs index runs_agent_created (agent, created_at) — 014_runs_agent_index.sql`
- context/layout.md: tree — `ui/` no longer planned: `src/{pages,components,components/ui,api,lib,styles}/  tests/  e2e/`; engine modules list gains `cards`, `events`; table rows: SSE event type → `engine/limo/common/constants.py` EVENT_TYPES + publish via `EventBus` (`engine/limo/events/bus.py`), UI page → `ui/src/pages/AgentsPage.tsx`, UI component → `ui/src/components/AgentCard.tsx`; Wiring: `ui/src/main.tsx` — query client + app (no router yet); Do not touch: `ui/src/components/ui/` (shadcn/ui) and `ui/src/api/schema.d.ts` (generated by `mise run gen:api`)
- context/stack.md: `ui/package-lock.json` pins exist (drop "planned"); key versions: React 19.3, Vite 8.4, Tailwind 4.3 (`@tailwindcss/vite`), react-query 5.108, Vitest 5.1, Playwright 1.65 + `@axe-core/playwright`, TypeScript 5.9.3 (held < 6.1 for typescript-eslint and openapi-typescript); `openapi-typescript` generates `ui/src/api/schema.d.ts`; dev servers: `mise run up` = `up:engine` + `up:ui` (vite proxies `/api` to `LIMO_API_URL`, default 127.0.0.1:8700)
- context/testing.md: Harness — UI component tests: `ui/tests/harness.tsx` (`serveCards`, `renderApp`, `card`, `FakeEventSource.emit`); UI e2e: `ui/playwright.config.ts` starts `engine/tests/e2e_app.py` (fakes, temp data dir) on 8701 and vite on 5174; engine SSE: `client.stream("GET", "/api/events")`, read `": connected"` first, then `next_event(lines, type)` (`tests/builders.py`) with `sse_heartbeat_s` short in the test's settings; commands: `mise run test:ui -- -t "FT-12.6"`, `mise run test:e2e`
- context/INDEX.md: Shape — add `- engine/limo/events — in-process EventBus; services publish, api/events.py streams SSE` and `- engine/limo/cards — agent card read model (one SQL query) → store`; remove "`ui` is (planned)"; Commands — add `test (ui): mise run test:ui` / `e2e: mise run test:e2e` / `api types: mise run gen:api`
- context/glossary.md: none (Agent card, Agent state already defined; code name `AgentState` used)
- context/code-rules.md: Quality gates — lint also runs `eslint` (complexity ≤ 10, max-lines 300, max-lines-per-function 40, max-params 5) + `prettier --check` in `ui/`; types also `tsc --noEmit` in `ui/`; dup also scans `ui/src` (ignores generated `schema.d.ts`, `components/ui/`)
- ARCHITECTURE.md: none (UI ↔ engine REST + SSE already drawn)
- adr: none
- adr/INDEX.md: none
