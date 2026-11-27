---
ticket: TKT-4
feature: limo
scenarios: [SC-10, SC-11, SC-12, SC-13, SC-54]
scope: [cost, persistence, api]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/cost.feature, work/limo/features/settings.feature, work/limo/questions.md#Q-7, work/limo/reports/TKT-3-verify-r1-1.md, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, ADR-3:L2, ADR-4:L2, engine/limo/agents/service.py, engine/limo/agents/models.py, engine/limo/agents/agent_service.py, engine/limo/app.py, engine/tests/fakes/llm.py]
---
# TKT-4: Every run records tokens and cost with totals

## Design
- where: new module `limo/cost/` (pricing, models, repo, service); `agents/service.py` records usage per Claude API call; `agents/models.py` Run gains tokens + cost; new `api/cost_routes.py`; migration `004_cost.sql`
- responsibilities:
  - `limo.cost.pricing` — money math in integer micro-dollars: `to_micros`, `format_usd`, `cost_micros`
  - `limo.cost.repo.PriceRepo` — `prices` table; `limo.cost.repo.UsageRepo` — `usage` table, run sums, project totals
  - `limo.cost.service.CostService` — set/list prices, record one call's usage with the price in effect now, run summary, project totals
  - `RunService` — after every Claude API call, `cost.record(...)`; `get` adds tokens + cost to the run
- reuse: `LlmUsage` (`llm/ports.py`); `ProjectRepo.get_by_name`; repo pattern (`agents/settings_repo.py`); `NotFound`
- contracts:
  - `PUT /api/prices/{model}` body `{"input": num, "output": num, "cache_read": num = 0, "cache_write": num = 0}` (USD per million tokens, each `0 ≤ x ≤ 1000`, `extra="forbid"`; `model` path matches `^[a-z0-9][a-z0-9.-]{0,63}$`) → 200 `Price` · 422 `validation_error`
  - `GET /api/prices` → 200 `[Price]` ordered by model
  - `Price` = `{"model", "input", "output", "cache_read", "cache_write"}`, each amount a decimal string with 6 places (e.g. `"4.000000"`)
  - `Run` gains `"tokens": {"input", "output", "cache_read", "cache_write"}` (ints) and `"cost": "<usd 6dp>"`
  - `GET /api/projects/{name}/costs` → 200 `{"per_agent": {agent: usd}, "per_ticket": {ticket: usd}, "per_agent_ticket": [{"agent", "ticket", "cost"}], "overall": usd}` · 404 `project_not_found`; runs without a ticket count under ticket key `"none"`; lists ordered by agent then ticket
  - pricing rule (Q-7): a call's cost is computed and stored when it is recorded, using the price at that moment; a model with no price costs 0 and the usage row has `priced = 0`
  - cost of one call = `round_half_up((input·p_in + output·p_out + cache_read·p_cr + cache_write·p_cw) / 1,000,000)` micro-dollars, prices in micro-dollars per million tokens
- data: `prices(model PK, input_micros, output_micros, cache_read_micros, cache_write_micros, updated_at)`; `usage(id, run_id, project_id, agent, feature, ticket, seq, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_micros, priced, created_at)` — agent/ticket/project copied onto each row so totals need no join with `runs`
- decisions: follows ADR-3 (plain SQL), ADR-4, data.md money as INTEGER micro-dollars · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a: single local user
- input validation: `PriceIn` bounds (0–1000) and `extra="forbid"`; model path pattern
- injection: parameterized SQL only in `cost/repo.py`
- data exposure / PII: none
- secrets: none
- rate limit / abuse: n/a: local
- audit: every API call's usage stored with time (`usage.created_at`)
### Performance
- queries (N+1, indexes): run summary = one `SUM` query; project totals = one `GROUP BY agent, ticket` query, aggregated in Python; index `usage(run_id)`, `usage(project_id)`
- pagination / limits: n/a: totals are aggregates
- payload size: n/a: small
- caching: n/a: none
- external calls (timeouts/retries): n/a: none added
- sync vs async: recording happens in the run worker thread
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 set price `PUT /api/prices/{model}` | FT-4.3 | FT-4.6 | n/a: upsert creates missing prices | n/a: upsert, no unique clash | n/a: prices can change any time; past usage keeps its cost (FT-4.4) | FT-4.7 | FT-4.8 | n/a: no external call |
| OP-2 list prices `GET /api/prices` | FT-4.7 | n/a: no parameters | n/a: list endpoint | n/a: read only | n/a: read only | n/a: read only | FT-4.12 | n/a: no external call |
| OP-3 cost totals `GET /api/projects/{name}/costs` | FT-4.5 | n/a: name is a path segment checked by lookup | FT-4.9 | n/a: read only | n/a: read only | n/a: read only | FT-4.10 | n/a: no external call |
| OP-4 record call usage (run loop) | FT-4.1 | n/a: usage comes from the Claude API response | FT-4.11 | n/a: one row per call | n/a: recorded only inside a running run | n/a: each call recorded once by seq | FT-4.2 | n/a: LLM failures covered by TKT-2 FT-2.9 |
| OP-5 get run `GET /api/runs/{id}` (tokens, cost) | FT-4.1 | n/a: covered by TKT-2 | n/a: covered by TKT-2 FT-2.8 | n/a: read only | n/a: read only | n/a: read only | n/a: single item | n/a: no external call |

## Functional tests
All in `engine/tests/functional/test_cost.py`. Money values are read as strings, e.g. `run["cost"] == "6.000000"`; errors as `r.json()["error"]["code"]`. A scripted response with usage: `final_with(LlmUsage(input_tokens=…, output_tokens=…, cache_read_tokens=…, cache_write_tokens=…))` (STEP-1). Opus price used below: `PUT /api/prices/claude-opus-5-5 {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 5}`.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-4.1 | SC-11, OP-4:happy, OP-5:happy | `engine/tests/functional/test_cost.py` | cart project; opus price; plan run scripted as 2 calls: `tool_use("list_files", {"path": "."})` with usage (10,000 in, 2,000 out, 0 cr, 8,000 cw), then `final_with` (3,000 in, 1,000 out, 8,000 cr, 0 cw) | `start_and_wait(client, "plan")` | run `model` "claude-opus-5-5"; `tokens` == `{"input": 13000, "output": 3000, "cache_read": 8000, "cache_write": 8000}` |
| FT-4.2 | SC-12, OP-4:boundary | `engine/tests/functional/test_cost.py` | cart project; opus price; plan run `final_with` (1,000,000 in, 100,000 out) | start plan run | run `cost` "6.000000" |
| FT-4.3 | SC-10, OP-1:happy | `engine/tests/functional/test_cost.py` | cart project; PUT `/api/agents/build/model` haiku; PUT `/api/prices/claude-haiku-5-5` `{"input": 0.10, "output": 0.50}` → 200 with `input` "0.100000"; build run `final_with` (2,000,000 in, 200,000 out) | start build run | run `cost` "0.300000" |
| FT-4.4 | SC-54 | `engine/tests/functional/test_cost.py` | as FT-4.2 (cost "6.000000") | PUT opus price `{"input": 8, "output": 40}` | GET the same run → `cost` still "6.000000" |
| FT-4.5 | SC-13, OP-3:happy | `engine/tests/functional/test_cost.py` | cart project; opus price; four runs with input tokens 250,000 (plan TKT-1 → 1.00), 50,000 (build TKT-1 → 0.20), 75,000 (build TKT-1 → 0.30), 500,000 (plan TKT-2 → 2.00), each one `final_with` call; `start_and_wait(client, agent, ticket)` | GET `/api/projects/shop/costs` | `per_agent` == `{"build": "0.500000", "plan": "3.000000"}`; `per_ticket` == `{"TKT-1": "1.500000", "TKT-2": "2.000000"}`; `per_agent_ticket` contains `{"agent": "build", "ticket": "TKT-1", "cost": "0.500000"}`; `overall` "3.500000" |
| FT-4.6 | OP-1:validation | `engine/tests/functional/test_cost.py` | fresh app | PUT opus `{"input": -1, "output": 1}`; `{"output": 1}`; `{"input": 1, "output": 1, "currency": "EUR"}`; PUT `/api/prices/Bad Model!` `{"input": 1, "output": 1}` | 422 `validation_error` each |
| FT-4.7 | OP-1:idempotency, OP-2:happy | `engine/tests/functional/test_cost.py` | fresh app | PUT opus `{"input": 4, "output": 20}` twice, then `{"input": 5, "output": 25}` | GET `/api/prices` → exactly one opus entry with `input` "5.000000", `output` "25.000000", `cache_read` "0.000000" |
| FT-4.8 | OP-1:boundary | `engine/tests/functional/test_cost.py` | fresh app | PUT `{"input": 0, "output": 1000}`; PUT `{"input": 1000.01, "output": 1}` | 200; 422 |
| FT-4.9 | OP-3:not-found | `engine/tests/functional/test_cost.py` | fresh app | GET `/api/projects/nope/costs` | 404 `project_not_found` |
| FT-4.10 | OP-3:boundary | `engine/tests/functional/test_cost.py` | cart project, no runs | GET `/api/projects/shop/costs` | `{"per_agent": {}, "per_ticket": {}, "per_agent_ticket": [], "overall": "0.000000"}` |
| FT-4.11 | OP-4:not-found | `engine/tests/functional/test_cost.py` | cart project, no prices; plan run `final_with` (1,000 in, 1,000 out) | start plan run | run `tokens.input` 1000, `cost` "0.000000" |
| FT-4.12 | OP-2:boundary | `engine/tests/functional/test_cost.py` | fresh app | GET `/api/prices` | 200 `[]` |

## Context pack
- `engine/tests/fakes/llm.py` — STEP-1 edit
- `engine/tests/builders.py`, `engine/tests/conftest.py` — read (helpers, fixtures)
- `engine/limo/llm/ports.py` — read (`LlmUsage`, `LlmResponse`)
- `engine/limo/agents/models.py` — STEP-7 edit
- `engine/limo/agents/service.py` — STEP-8 edit
- `engine/limo/agents/agent_service.py` — STEP-8 edit (remove `model_for`)
- `engine/limo/agents/settings_repo.py` — like: repository pattern
- `engine/limo/projects/repo.py` — read (`get_by_name`)
- `engine/limo/common/errors.py` — read
- `engine/limo/store/db.py` — read (`connect`)
- `engine/limo/api/agents_routes.py` — like: router factory
- `engine/limo/app.py` — STEP-10 edit

## Steps
### STEP-1 fake LLM: usage helper and model echo
- file: `engine/tests/fakes/llm.py` (edit)
- do: add `def final_with(usage: LlmUsage, text: str = "done") -> LlmResponse` (same as `final` but with that usage); give `tool_use` an optional `usage: LlmUsage | None = None` parameter (default `LlmUsage()`); in `FakeLlm.create`, when the response's `model` is `"fake"`, return `dataclasses.replace(response, model=request.model)` (also for `repeat` and `final()`).
- verify: `mise run test:engine` → 35 passed (no behavior change)

### STEP-2 tests (test first)
- file: `engine/tests/functional/test_cost.py` (create)
- do: one function per FT-4.1 … FT-4.12 per the table; names `test_ft_4_<k>_<behavior>`, docstring starts `"""FT-4.<k> `. Script runs with `llm.script = [...]` before `start_and_wait`. Read results exactly as stated above the table.
- verify: `mise run test:engine -- -k ft_4` → FAIL (404 on `/api/prices…`)

### STEP-3 tables
- file: `engine/limo/store/migrations/004_cost.sql` (create)
```sql
CREATE TABLE prices (
  model TEXT PRIMARY KEY,
  input_micros INTEGER NOT NULL,
  output_micros INTEGER NOT NULL,
  cache_read_micros INTEGER NOT NULL,
  cache_write_micros INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  agent TEXT NOT NULL,
  feature TEXT NOT NULL,
  ticket TEXT,
  seq INTEGER NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL,
  cache_write_tokens INTEGER NOT NULL,
  cost_micros INTEGER NOT NULL,
  priced INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX usage_run ON usage (run_id);
CREATE INDEX usage_project ON usage (project_id);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-4 pricing math
- file: `engine/limo/cost/__init__.py` (empty), `engine/limo/cost/pricing.py` (create)
```python
from dataclasses import dataclass

from limo.llm.ports import LlmUsage

MICROS = 1_000_000


@dataclass(frozen=True)
class PriceMicros:
    """USD micro-dollars per million tokens."""

    input: int
    output: int
    cache_read: int
    cache_write: int


def to_micros(usd: float) -> int:
    return round(usd * MICROS)


def format_usd(micros: int) -> str:
    return f"{micros // MICROS}.{micros % MICROS:06d}"


def cost_micros(usage: LlmUsage, price: PriceMicros | None) -> int:
    if price is None:
        return 0
    total = (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_read_tokens * price.cache_read
        + usage.cache_write_tokens * price.cache_write
    )
    return (total + MICROS // 2) // MICROS
```
- verify: `cd engine && uv run python -c "from limo.cost.pricing import *; from limo.llm.ports import LlmUsage as U; print(format_usd(cost_micros(U(1_000_000, 100_000), PriceMicros(4_000_000, 20_000_000, 0, 0))))"` → `6.000000`

### STEP-5 models
- file: `engine/limo/cost/models.py` (create)
- do: `PriceIn` (`extra="forbid"`; `input: float = Field(ge=0, le=1000)`, `output` same, `cache_read: float = Field(default=0, ge=0, le=1000)`, `cache_write` same); `Price` (`model: str` + four `str` amounts); `TokenCounts` (`input, output, cache_read, cache_write: int`); `AgentTicketCost` (`agent: str`, `ticket: str`, `cost: str`); `CostTotals` (`per_agent: dict[str, str]`, `per_ticket: dict[str, str]`, `per_agent_ticket: list[AgentTicketCost]`, `overall: str`)
- verify: `cd engine && uv run python -c "import limo.cost.models"` → exit 0

### STEP-6 repos and service
- file: `engine/limo/cost/repo.py`, `engine/limo/cost/service.py` (create)
- do:
  - `PriceRepo(db_path)`: `get(model) -> PriceMicros | None`; `set(model, PriceMicros)` (upsert like `agents/settings_repo.py`); `list() -> list[tuple[str, PriceMicros]]` ordered by model
  - `@dataclass(frozen=True) UsageRow`: `run_id, project_id, agent, feature, ticket (str | None), seq, model, usage: LlmUsage, cost_micros, priced: bool`
  - `UsageRepo(db_path)`: `add(row: UsageRow)`; `run_sum(run_id) -> tuple[TokenCounts, int]` (one `SELECT COALESCE(SUM(...),0)…`); `project_rows(project_id) -> list[tuple[str, str | None, int]]` = `SELECT agent, ticket, SUM(cost_micros) … GROUP BY agent, ticket ORDER BY agent, ticket`
  - `CostService(prices: PriceRepo, usage: UsageRepo, projects: ProjectRepo)`:
    - `set_price(model, data: PriceIn) -> Price`; `list_prices() -> list[Price]` (amounts via `format_usd`)
    - frozen dataclass `CallRef(run_id: str, project_id: str, agent: str, feature: str, ticket: str | None)` in `cost/service.py` (keeps `record` at ≤ 5 params and avoids importing `limo.agents`)
    - `record(ref: CallRef, seq: int, model: str, usage: LlmUsage) -> None`: `price = prices.get(model)`; add a `UsageRow` with `cost_micros(usage, price)` and `priced = price is not None`
    - `run_summary(run_id) -> tuple[TokenCounts, str]`
    - `totals(project_name) -> CostTotals`: project missing → `NotFound("project_not_found", …)`; build the dicts from `project_rows` (ticket `None` → `"none"`), sum in micros, format at the end
- verify: `cd engine && uv run python -c "import limo.cost.service"` → exit 0

### STEP-7 run gains tokens and cost
- file: `engine/limo/agents/models.py` (edit)
- do: import `TokenCounts` from `limo.cost.models`; add to `Run`: `tokens: TokenCounts | None = None`, `cost: str | None = None`
- verify: `cd engine && uv run python -c "import limo.agents.models"` → exit 0

### STEP-8 record usage in the run loop; drop unused method
- file: `engine/limo/agents/service.py` (edit), `engine/limo/agents/agent_service.py` (edit)
- do:
  - `RunStores` gains `cost: CostService`
  - in `_run`, after the project lookup, build `ref = CallRef(run.id, project.id, run.agent, run.feature, run.ticket)` and pass it to `_loop` (signature `_loop(self, run, ctx, ref)`)
  - in `_loop`, keep `call_no = 0`; right after `resp = self._llm.create(request)`: `call_no += 1; self._stores.cost.record(ref, call_no, resp.model, resp.usage)`
  - `get(run_id)`: after loading the run, `tokens, cost = self._stores.cost.run_summary(run_id)` and return `run.model_copy(update={"tokens": tokens, "cost": cost})`
  - delete `AgentService.model_for` (unused; verify TKT-3 R-1)
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-9 routes
- file: `engine/limo/api/cost_routes.py` (create)
- do: `cost_router(service: CostService) -> APIRouter` (no prefix): `PUT /api/prices/{model}` (`Price`; path param `model: str = Path(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")`, body `PriceIn`), `GET /api/prices` (`list[Price]`), `GET /api/projects/{name}/costs` (`CostTotals`); plain `def` handlers
- verify: `cd engine && uv run python -c "import limo.api.cost_routes"` → exit 0

### STEP-10 wiring
- file: `engine/limo/app.py` (edit)
- do: `cost = CostService(PriceRepo(db), UsageRepo(db), ProjectRepo(db))`; pass `cost` as the new last field of `RunStores`; `app.include_router(cost_router(cost))`
- verify: `mise run test:engine` → 47 passed (35 + 12)

### STEP-11 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 47 passed

## Do not
- add budgets, UI, or SSE
- change how runs pick their model
- recompute stored costs when prices change
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/cost` — prices, usage, totals → `store` (no longer planned)
- context/data.md: Main entities — `prices`, `usage` columns per `004_cost.sql`; money rule: cost fixed at record time (Q-7)
- context/api.md: Reference implementations — cost: `engine/limo/api/cost_routes.py` (`PUT/GET /api/prices`, `GET /api/projects/{name}/costs`)
- context/layout.md: Tree module list adds `cost`
- context/testing.md: Fakes — `final_with(usage)`, `tool_use(..., usage=)`; FakeLlm echoes the request model
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
