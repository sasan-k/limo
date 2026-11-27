---
ticket: TKT-17
feature: limo
scenarios: [SC-55, SC-56, SC-57, SC-58]
scope: [cost, runner, api]
revision: 2  # past the re-plan limit; started by the orchestrator under "keep going", flagged to the user
run: from-STEP-12
read: [work/limo/map.yaml, work/limo/features/budget.feature, work/limo/questions.md#Q-12, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, ADR-3:L2, ADR-4:L2, engine/limo/agents/service.py, engine/limo/cost/repo.py, engine/limo/cost/service.py, engine/limo/cost/pricing.py, engine/limo/runner/service.py, engine/limo/app.py, engine/limo/config.py, engine/tests/builders.py]
---
# TKT-17: Ticket and agent budgets stop work and can be raised

## Design
- where: new modules `limo/budget/` (defaults, per-ticket overrides, spend check) and `limo/inbox/` (holds: tickets waiting for a human); run loop checks budgets after each Claude API call; runner skips held tickets and can continue a hold; routes `budget_routes.py`, `inbox_routes.py`; migration `006_budgets_holds.sql`
- responsibilities:
  - `limo.budget.service.BudgetService` — default budgets, per-ticket overrides (ticket-level and per agent), `status(project, feature, ticket)`, `exceeded(ref) -> str | None`
  - `limo.inbox.service.InboxService` — open a hold, list open holds, clear a hold, open-hold tickets of a feature
  - `RunService._loop` — after `cost.record`, `budget.exceeded(ref)` → finish the run `failed` with `budget: <reason>`, open a `budget` hold, no further Claude API call
  - `RunnerService` — skips tickets with an open hold; `continue_hold(hold_id)` clears it and takes one step
- reuse: `UsageRepo` sums (`cost/repo.py`), `format_usd`/`to_micros` (`cost/pricing.py`), `CallRef` (`cost/service.py`), repo pattern, `RunnerService.step`
- contracts:
  - `PUT /api/budgets/defaults` `{"ticket": num, "agent": num}` (USD, `0 < x ≤ 10000`, `extra="forbid"`) → 200 `{"ticket": usd, "agent": usd}`; `GET /api/budgets/defaults` → same shape (initial: `settings.default_ticket_budget` 10.00, `settings.default_agent_budget` 5.00)
  - `PUT /api/projects/{name}/features/{feature}/tickets/{ticket}/budget` `{"amount": num, "agent": AgentName | null}` → 200 `TicketBudget`; `agent` null = the ticket budget, else that agent's budget on this ticket
  - `GET /api/projects/{name}/features/{feature}/tickets/{ticket}/budget` → 200 `TicketBudget` = `{"ticket": {"budget": usd, "spent": usd}, "agents": {<each of the 7 agents>: {"budget": usd, "spent": usd}}}`
  - both ticket endpoints: 404 `project_not_found`; 422 for bad feature/ticket/agent/amount (ticket `^TKT-\d+$`, feature `^[a-z0-9][a-z0-9-]{0,39}$`)
  - `GET /api/inbox` → 200 `[Hold]` open holds, oldest first; `Hold` = `{"id", "project", "feature", "ticket", "kind": "budget", "reason", "created_at"}`
  - `POST /api/inbox/{id}/continue` → 200 `StepResult` (from the runner, after clearing the hold) · 404 `hold_not_found` · 409 `hold_cleared` (already continued)
  - reason texts (dollars to cents, `$X.YY`): `ticket budget reached: $<spent> of $<budget>`; `<agent> budget reached: $<spent> of $<budget>`; ticket checked first
  - "reached" = spent ≥ budget
  - runner: ticket ids with an open hold are skipped both for in-progress dispatch and for `ready`
- data: `budget_defaults(id = 1, ticket_micros, agent_micros)`; `ticket_budgets(project_id, feature, ticket, agent ('' = ticket), budget_micros, PK(project_id, feature, ticket, agent))`; `holds(id, project_id, feature, ticket, kind, reason, created_at, cleared_at)`; spend = `SUM(usage.cost_micros)` by (project_id, feature, ticket[, agent])
- decisions: follows ADR-3, ADR-4; holds are the shared "waiting for a human" record that escalations (TKT-10) will reuse · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a: single local user
- input validation: pydantic models with bounds, patterns, `extra="forbid"`; agent must be one of the seven
- injection: parameterized SQL in `budget/repo.py`, `inbox/repo.py`
- data exposure / PII: none
- secrets: none
- rate limit / abuse: this ticket is the spend limiter: a run stops right after the call that reaches a budget
- audit: holds keep `created_at` / `cleared_at`
### Performance
- queries (N+1, indexes): budget check = 2 `SUM` queries per API call; index `usage(project_id, feature, ticket, agent)`; status view = 1 grouped query for agent spend
- pagination / limits: inbox holds are few; no pagination
- payload size: n/a
- caching: n/a: none
- external calls (timeouts/retries): n/a
- sync vs async: check runs in the worker thread
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 set defaults `PUT /api/budgets/defaults` | FT-17.1 | FT-17.6 | n/a: singleton | n/a: upsert | n/a: allowed any time | FT-17.7 | FT-17.8 | n/a: no external call |
| OP-2 ticket budget `GET …/tickets/{ticket}/budget` | FT-17.1 | n/a: path patterns covered by FT-17.9 | FT-17.10 | n/a: read only | n/a: read only | n/a: read only | FT-17.11 | n/a: no external call |
| OP-3 override `PUT …/tickets/{ticket}/budget` | FT-17.4 | FT-17.9 | FT-17.10 | n/a: upsert | n/a: allowed any time | FT-17.7 | FT-17.8 | n/a: no external call |
| OP-4 budget check (run loop) | FT-17.2 | n/a: inputs are stored numbers | n/a: no override → defaults (FT-17.1) | n/a: one check per call | FT-17.3 | n/a: check is read-only | FT-17.12 | n/a: no external call |
| OP-5 inbox `GET /api/inbox` | FT-17.2 | n/a: no parameters | n/a: list | n/a: read only | n/a: read only | n/a: read only | FT-17.11 | n/a: no external call |
| OP-6 continue `POST /api/inbox/{id}/continue` | FT-17.4 | n/a: id is opaque | FT-17.13 | FT-17.13 | FT-17.5 | n/a: a second continue is `hold_cleared` (FT-17.13) | n/a: single item | n/a: no external call |

## Functional tests
All in `engine/tests/functional/test_budget.py`. Opus price `{"input": 4, "output": 20}` is set in every test that runs agents. Read money as strings (`"5.000000"`), reasons as exact text, errors as `r.json()["error"]["code"]`. Ticket statuses via `set_status`; runs via `start_and_wait` or the runner step. Paths: `B = "/api/projects/shop/features/cart/tickets/TKT-1/budget"`; runner step = `POST /api/projects/shop/features/cart/step` → `{"run": Run | null, "reason": "started" | "run_active" | "no_ready_ticket"}`; continue returns that same shape.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-17.1 | SC-55, OP-1:happy, OP-2:happy | `engine/tests/functional/test_budget.py` | cart project | PUT defaults `{"ticket": 5, "agent": 2}`; GET `B` | defaults body `{"ticket": "5.000000", "agent": "2.000000"}`; `ticket.budget` "5.000000", `agents.build.budget` "2.000000", `ticket.spent` "0.000000" |
| FT-17.2 | SC-56, OP-4:happy, OP-5:happy | `engine/tests/functional/test_budget.py` | defaults ticket 5, agent 100; plan run for TKT-1 `final_with` 1,225,000 input (= 4.90); then `llm.script = [tool_use("read_file", {"path": "src/cart.py"}, usage=LlmUsage(output_tokens=50_000))]` | `start_and_wait(client, "build")` | run `failed`, `error` starts `budget:`; the build run made exactly 1 LLM request; GET `/api/inbox` → one hold `{"ticket": "TKT-1", "kind": "budget", "reason": "ticket budget reached: $5.90 of $5.00"}`; no run with agent `resolver` exists (`GET /api/runs/{id}` of started runs only plan/build) |
| FT-17.3 | SC-57, OP-4:invalid-state | `engine/tests/functional/test_budget.py` | defaults ticket 100, agent 2; build run 1 `final_with` 487,500 input (= 1.95) succeeds; then build run 2 `tool_use("read_file", …, usage=LlmUsage(output_tokens=5_000))` | `start_and_wait(client, "build")` (2nd) | run `failed`; 1 LLM request in that run; inbox reason `"build budget reached: $2.05 of $2.00"` |
| FT-17.4 | SC-58, OP-3:happy, OP-6:happy | `engine/tests/functional/test_budget.py` | state of FT-17.2; `set_status(…, "TKT-1", "planned")` | PUT `B` `{"amount": 8, "agent": null}`; POST `/api/inbox/{id}/continue` | PUT → `ticket.budget` "8.000000"; continue → `reason` "started", `run.agent` "build", `run.ticket` "TKT-1"; GET `/api/inbox` → `[]` |
| FT-17.5 | OP-6:invalid-state (runner skips held) | `engine/tests/functional/test_budget.py` | state of FT-17.2; `set_status(…, "TKT-1", "planned")`; TKT-3 `done` | POST runner step for `cart` | `run` null, `reason` "no_ready_ticket" (TKT-1 held, TKT-2 waits on TKT-1) |
| FT-17.6 | OP-1:validation | `engine/tests/functional/test_budget.py` | fresh app | PUT defaults `{"ticket": 0, "agent": 1}`; `{"ticket": 1}`; `{"ticket": 1, "agent": 1, "x": 1}` | 422 each |
| FT-17.7 | OP-1:idempotency, OP-3:idempotency | `engine/tests/functional/test_budget.py` | cart project | PUT defaults `{"ticket": 3, "agent": 1}` twice; PUT `B` `{"amount": 4, "agent": "build"}` twice | same bodies both times; GET `B` → `agents.build.budget` "4.000000", `ticket.budget` "3.000000" |
| FT-17.8 | OP-1:boundary, OP-3:boundary | `engine/tests/functional/test_budget.py` | cart project | PUT defaults `{"ticket": 10000, "agent": 0.01}`; `{"ticket": 10000.01, "agent": 1}`; PUT `B` `{"amount": 0.01, "agent": null}` | 200; 422; 200 |
| FT-17.9 | OP-3:validation | `engine/tests/functional/test_budget.py` | cart project | PUT `B` `{"amount": 1, "agent": "deploy"}`; PUT `…/tickets/T1/budget` `{"amount": 1, "agent": null}`; PUT `B` `{"amount": -1, "agent": null}` | 422 each |
| FT-17.10 | OP-2:not-found, OP-3:not-found | `engine/tests/functional/test_budget.py` | fresh app | GET and PUT `/api/projects/nope/features/cart/tickets/TKT-1/budget` | 404 `project_not_found` each |
| FT-17.11 | OP-2:boundary, OP-5:boundary | `engine/tests/functional/test_budget.py` | cart project, no runs | GET `B`; GET `/api/inbox` | all 7 agents present with `spent` "0.000000"; inbox `[]` |
| FT-17.12 | OP-4:boundary | `engine/tests/functional/test_budget.py` | defaults ticket 1, agent 100 | plan run `final_with` 247,500 input (= 0.99); then a 2nd plan run `final_with` 750 input (= 0.003 → total 0.993) ; then a 3rd plan run `final_with` 1,750 input (total ≥ 1.00) | 1st and 2nd runs `succeeded`, inbox `[]` after them; 3rd run `failed` with `error` starting `budget:` and inbox reason `"ticket budget reached: $1.00 of $1.00"` (reached = spent ≥ budget; checked after each call, before the run finishes) |
| FT-17.13 | OP-6:not-found, OP-6:conflict | `engine/tests/functional/test_budget.py` | state of FT-17.2 | POST `/api/inbox/nope/continue`; POST continue on the real hold twice | 404 `hold_not_found`; 1st 200, 2nd 409 `hold_cleared` |

## Context pack
- `engine/limo/agents/service.py` — STEP-7 edit
- `engine/limo/cost/repo.py` — STEP-4 edit (spend sums)
- `engine/limo/cost/pricing.py`, `engine/limo/cost/service.py` — read (`format_usd`, `to_micros`, `CallRef`)
- `engine/limo/cost/models.py` — like: money as strings
- `engine/limo/runner/service.py`, `engine/limo/runner/models.py` — STEP-8 edit / read
- `engine/limo/agents/settings_repo.py` — like: upsert repository
- `engine/limo/api/cost_routes.py` — like: router with path patterns
- `engine/limo/common/errors.py`, `engine/limo/common/constants.py`, `engine/limo/store/db.py`, `engine/limo/projects/repo.py` — read
- `engine/limo/config.py` — STEP-3 edit
- `engine/limo/app.py` — STEP-10 edit
- `engine/tests/builders.py`, `engine/tests/conftest.py`, `engine/tests/fakes/llm.py` — read
- `engine/tests/functional/test_budget.py` — STEP-13 edit

## Steps
### STEP-1 tests (test first)
- file: `engine/tests/functional/test_budget.py` (create)
- do: one function per FT-17.1 … FT-17.13; names `test_ft_17_<k>_<behavior>`, docstring starts `"""FT-17.<k> `. Shared setup for FT-17.2/4/5/13 in a local helper `_reach_ticket_budget(client, llm, settings, tmp_path) -> str` (returns the hold id). LLM requests of one run = `len(llm.requests)` difference before/after it.
- verify: `mise run test:engine -- -k ft_17` → FAIL (404 on `/api/budgets/defaults`)

### STEP-2 tables
- file: `engine/limo/store/migrations/006_budgets_holds.sql` (create)
```sql
CREATE TABLE budget_defaults (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  ticket_micros INTEGER NOT NULL,
  agent_micros INTEGER NOT NULL
);

CREATE TABLE ticket_budgets (
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  agent TEXT NOT NULL,
  budget_micros INTEGER NOT NULL,
  PRIMARY KEY (project_id, feature, ticket, agent)
);

CREATE TABLE holds (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('budget')),
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  cleared_at TEXT
);
CREATE INDEX holds_open ON holds (project_id, feature, cleared_at);
CREATE INDEX usage_ticket_agent ON usage (project_id, feature, ticket, agent);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-3 settings
- file: `engine/limo/config.py` (edit)
- do: add `default_ticket_budget: float = 10.0`, `default_agent_budget: float = 5.0`
- verify: `cd engine && uv run python -c "from limo.config import Settings; print(Settings(_env_file=None).default_ticket_budget)"` → `10.0`

### STEP-4 spend sums
- file: `engine/limo/cost/repo.py` (edit)
- do: add to `UsageRepo`: `ticket_spent(project_id, feature, ticket) -> int` and `agent_spent(project_id, feature, ticket) -> dict[str, int]` (one `GROUP BY agent` query); both `COALESCE(SUM(cost_micros), 0)`
- verify: `cd engine && uv run python -c "import limo.cost.repo"` → exit 0

### STEP-5 budget module
- file: `engine/limo/budget/__init__.py` (empty), `models.py`, `repo.py`, `service.py` (create)
- do:
  - models: `DefaultsIn` (`ticket`, `agent`: `float = Field(gt=0, le=10000)`, `extra="forbid"`); `Defaults` (`ticket: str`, `agent: str`); `BudgetIn` (`amount: float = Field(gt=0, le=10000)`, `agent: AgentName | None = None` where `AgentName = Literal["architecture", "spec", "plan", "build", "verify", "close", "resolver"]`, `extra="forbid"`); `Line` (`budget: str`, `spent: str`); `TicketBudget` (`ticket: Line`, `agents: dict[str, Line]`)
  - repo `BudgetRepo(db_path)`: `defaults() -> tuple[int, int] | None`; `set_defaults(ticket_micros, agent_micros)` (`INSERT … ON CONFLICT(id) DO UPDATE`, id = 1); `overrides(project_id, feature, ticket) -> dict[str, int]` (key `""` = ticket level); `set_override(key: BudgetKey, agent: str, micros: int)` where `@dataclass(frozen=True) BudgetKey(project_id, feature, ticket)`
  - service `BudgetService(repo: BudgetRepo, usage: UsageRepo, projects: ProjectRepo, fallback: tuple[int, int])` (`fallback` = settings defaults in micros):
    - `get_defaults() -> Defaults`, `set_defaults(DefaultsIn) -> Defaults`
    - `status(project_name, feature, ticket) -> TicketBudget` (project missing → `NotFound("project_not_found", …)`); every agent in `AGENT_NAMES` listed
    - `set_budget(project_name, feature, ticket, data: BudgetIn) -> TicketBudget`
    - `exceeded(ref: CallRef) -> str | None`: ticket limit first, then `ref.agent`'s limit; uses `_dollars(micros) = f"${(micros + 5_000) // 10_000 // 100}.{(micros + 5_000) // 10_000 % 100:02d}"`; returns the reason text or None; `ref.ticket` None → None
- verify: `cd engine && uv run python -c "import limo.budget.service"` → exit 0

### STEP-6 inbox module
- file: `engine/limo/inbox/__init__.py` (empty), `models.py`, `repo.py`, `service.py` (create)
- do:
  - models: `Hold` (`id, project, feature, ticket, kind: Literal["budget"], reason, created_at`)
  - repo `HoldRepo(db_path)`: `add(project_id, ref_feature_ticket…)` — use a frozen dataclass `NewHold(project_id, feature, ticket, kind, reason)` as its one argument; `open_list() -> list[Hold]` (join `projects` for the name, `cleared_at IS NULL`, order `created_at`); `get(hold_id) -> tuple[Hold, str | None] | None` (hold + cleared_at); `clear(hold_id)`; `open_tickets(project_id, feature) -> set[str]`
  - service `InboxService(repo: HoldRepo)`: `hold(NewHold) -> None`; `list() -> list[Hold]`; `take(hold_id) -> Hold` (missing → `NotFound("hold_not_found", …)`; already cleared → `Conflict("hold_cleared", …)`; else clear and return it); `held_tickets(project_id, feature) -> set[str]`
- verify: `cd engine && uv run python -c "import limo.inbox.service"` → exit 0

### STEP-7 budget check in the run loop
- file: `engine/limo/agents/service.py` (edit)
- do: `RunStores` gains `budget: BudgetService` and `inbox: InboxService`. In `_loop`, right after `self._stores.cost.record(...)`: `reason = self._stores.budget.exceeded(ref)`; if reason: `self._stores.inbox.hold(NewHold(ref.project_id, ref.feature, ref.ticket, "budget", reason))` (only when `ref.ticket` is set), `self._stores.runs.finish(run.id, "failed", None, f"budget: {reason}")`, `return`. Keep `_loop` ≤ 40 lines: move the stop into a private `_stop_for_budget(run, ref, reason)`.
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-8 runner skips holds and continues
- file: `engine/limo/runner/service.py` (edit)
- do: constructor gains `inbox: InboxService` (replace the `max_concurrent: int` param by a frozen dataclass `RunnerConfig(max_concurrent: int)` if needed to stay ≤ 5 params incl. self). In `step`, after `board.read`: `held = inbox.held_tickets(project.id, feature)`; drop states and ready ids in `held`. Add `continue_hold(hold_id) -> StepResult`: `hold = inbox.take(hold_id)`; `return self.step(hold.project, hold.feature)`.
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-9 routes
- file: `engine/limo/api/budget_routes.py`, `engine/limo/api/inbox_routes.py` (create)
- do: `budget_router(service: BudgetService)`: `GET/PUT /api/budgets/defaults`, `GET/PUT /api/projects/{name}/features/{feature}/tickets/{ticket}/budget` (feature and ticket `Annotated[str, Path(pattern=…)]`). `inbox_router(inbox: InboxService, runner: RunnerService)`: `GET /api/inbox` → `inbox.list()`; `POST /api/inbox/{hold_id}/continue` → `runner.continue_hold(hold_id)`.
- verify: `cd engine && uv run python -c "import limo.api.budget_routes, limo.api.inbox_routes"` → exit 0

### STEP-10 wiring
- file: `engine/limo/app.py` (edit)
- do: build `usage = UsageRepo(db)` once and reuse it for `CostService` and `BudgetService(BudgetRepo(db), usage, ProjectRepo(db), (to_micros(settings.default_ticket_budget), to_micros(settings.default_agent_budget)))`; `inbox = InboxService(HoldRepo(db))`; pass `budget`, `inbox` into `RunStores`; pass `inbox` to `RunnerService`; include both routers
- verify: `mise run test:engine` → all pass (60 earlier + 13 FT-17)

### STEP-11 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 73 passed

### STEP-12 typed sums (revision 2)
- file: `engine/limo/cost/repo.py` (edit)
- do: in `ticket_spent` return `int(row[0])`; in `agent_spent` build the dict as `{str(r[0]): int(r[1]) for r in rows}`
- verify: `mise run types` → `Success`

### STEP-13 FT-17.2 checks no resolver run (revision 2)
- file: `engine/tests/functional/test_budget.py` (edit)
- do: in FT-17.2 add: every request recorded by the fake LLM during the test has a `system` different from `(settings.skills_dir / "resolver" / "SKILL.md").read_text()`
- verify: `mise run test:engine -- -k ft_17_2` → passed

### STEP-14 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 73 passed

## Do not
- run the resolver, escalate on the repo host, or add UI
- change prices or recorded costs
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/budget` (defaults, overrides, spend check) and `engine/limo/inbox` (holds waiting for a human)
- context/layout.md: module list adds `budget`, `inbox`
- context/api.md: budget and inbox endpoints
- context/data.md: `budget_defaults`, `ticket_budgets`, `holds`; index `usage_ticket_agent`
- context/glossary.md: Hold — a ticket waiting for a human (budget now; escalation later) — `Hold`
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
