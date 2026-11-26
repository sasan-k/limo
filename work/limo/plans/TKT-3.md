---
ticket: TKT-3
feature: limo
scenarios: [SC-8, SC-9]
scope: [api, agents, persistence]
revision: 1
run: from-STEP-9
read: [work/limo/map.yaml, work/limo/features/settings.feature, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, context/adr/INDEX.md, ADR-3:L2, ADR-4:L2, ADR-6:L2, engine/limo/agents/service.py, engine/limo/agents/models.py, engine/limo/api/agents_routes.py, engine/limo/app.py, engine/limo/store/migrations/]
---
# TKT-3: Each agent runs on its configured model

## Design
- where: `limo/agents` (settings repo, agent service), `api/agents_routes.py`, `app.py`, migration `003_agent_settings.sql`
- responsibilities:
  - `limo.agents.settings_repo.AgentSettingsRepo` — SQL for `agent_settings` (model per agent)
  - `limo.agents.agent_service.AgentService` — list agents with their effective model; set an agent's model
  - `RunService.start` — reads the agent's model when the run is created (stored on the run)
- reuse: `AgentRegistry` (`agents/registry.py`) for names/prompt/references; repo pattern `agents/repo.py`; `NotFound` (`common/errors.py`); `AGENT_NAMES`
- contracts:
  - `GET /api/agents` → each item gains `"model": str` (configured model, else `settings.default_model`)
  - `PUT /api/agents/{name}/model` body `{"model": ^[a-z0-9][a-z0-9.-]{0,63}$}` (`extra="forbid"`) → 200 `Agent` · 404 `agent_not_found` · 422 `validation_error`
  - a run's `model` = the agent's model at the time the run is started (later changes do not alter queued/finished runs)
- data: `agent_settings(agent TEXT PRIMARY KEY, model TEXT NOT NULL, updated_at TEXT NOT NULL)`
- decisions: follows ADR-3, ADR-4, ADR-6 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a: single local user
- input validation: `ModelIn` pydantic with pattern + `extra="forbid"`; agent name checked against `AGENT_NAMES` → 404
- injection: parameterized SQL (`INSERT … ON CONFLICT(agent) DO UPDATE`)
- data exposure / PII: none
- secrets: none
- rate limit / abuse: n/a: local single user
- audit: n/a: `updated_at` kept on the row; audit log arrives with the runner
### Performance
- queries (N+1, indexes): list = one `SELECT agent, model FROM agent_settings` merged in memory (7 rows); PK lookup at run start
- pagination / limits: n/a: fixed 7 agents
- payload size: n/a: tiny
- caching: n/a: none
- external calls (timeouts/retries): n/a: none
- sync vs async: sync handlers in threadpool
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 set agent model `PUT /api/agents/{name}/model` | FT-3.1 | FT-3.3 | FT-3.4 | n/a: upsert, no unique clash | n/a: model can change at any time; runs keep the model they started with (FT-3.2) | FT-3.5 | FT-3.6 | n/a: no external call |
| OP-2 list agents `GET /api/agents` | FT-3.1 | n/a: no parameters | n/a: fixed list | n/a: read only | n/a: read only | n/a: read only | FT-3.7 | n/a: no external call |
| OP-3 start run `POST /api/projects/{name}/runs` (model lookup) | FT-3.2 | n/a: body unchanged, covered by TKT-2 | n/a: covered by TKT-2 | n/a: covered by TKT-2 | n/a: covered by TKT-2 | n/a: covered by TKT-2 | n/a: covered by TKT-2 | n/a: covered by TKT-2 |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-3.1 | SC-8, OP-1:happy, OP-2:happy | `engine/tests/functional/test_agent_settings.py` | fresh app | PUT `/api/agents/build/model` `{"model": "claude-haiku-5-5"}` | 200 with `model` "claude-haiku-5-5"; GET `/api/agents` → build has model "claude-haiku-5-5", plan has `settings.default_model` |
| FT-3.2 | SC-9, OP-3:happy | `engine/tests/functional/test_agent_settings.py` | cart project (`add_cart_project`); build model set to "claude-haiku-5-5" | `start_and_wait(client, "build")`; then set build model to "claude-sonnet-5-5" | fake LLM's first request `model` == "claude-haiku-5-5"; GET run → `model` "claude-haiku-5-5" (unchanged after the later PUT) |
| FT-3.3 | OP-1:validation | `engine/tests/functional/test_agent_settings.py` | fresh app | PUT model `"Claude Haiku!"`; PUT `{"model": "x", "temperature": 1}`; PUT `{}` | 422 `validation_error` each |
| FT-3.4 | OP-1:not-found | `engine/tests/functional/test_agent_settings.py` | fresh app | PUT `/api/agents/deploy/model` `{"model": "claude-haiku-5-5"}` | 404 `agent_not_found` |
| FT-3.5 | OP-1:idempotency | `engine/tests/functional/test_agent_settings.py` | fresh app | PUT the same model for build twice | both 200 with the same body; GET shows it once |
| FT-3.6 | OP-1:boundary | `engine/tests/functional/test_agent_settings.py` | fresh app | PUT a 64-char model `"a" * 64`; PUT a 65-char model | 200; 422 |
| FT-3.7 | OP-2:boundary | `engine/tests/functional/test_agent_settings.py` | fresh app, nothing set | GET `/api/agents` | all 7 agents have `model` == `settings.default_model` |

## Context pack
- `engine/limo/agents/models.py` — STEP-3 edit
- `engine/limo/agents/registry.py` — read (builds `Agent` without model)
- `engine/limo/agents/repo.py` — like: repository pattern
- `engine/limo/agents/service.py`:1-60 — STEP-6 edit (`RunStores`, `start`)
- `engine/limo/api/agents_routes.py` — STEP-5 edit
- `engine/limo/app.py` — STEP-7 edit
- `engine/limo/common/errors.py` — read
- `engine/limo/common/constants.py` — read
- `engine/limo/store/db.py` — read (`connect`)
- `engine/tests/conftest.py`, `engine/tests/builders.py`, `engine/tests/fakes/llm.py` — read (fixtures, helpers)
- `engine/tests/functional/test_agent_settings.py` — STEP-9 edit

## Steps
### STEP-1 tests (test first)
- file: `engine/tests/functional/test_agent_settings.py` (create)
- do: one function per FT-3.1 … FT-3.7 per the table; names `test_ft_3_<k>_<behavior>`, docstring starts `"""FT-3.<k> `. Use fixtures `client`, `llm`, `settings`, `tmp_path`; helpers `add_cart_project`, `start_and_wait` from `tests.builders`. FT-3.2 reads `llm.requests[0].model`.
- verify: `mise run test:engine -- -k ft_3` → FAIL (PUT returns 405 / `model` key missing)

### STEP-2 table
- file: `engine/limo/store/migrations/003_agent_settings.sql` (create)
```sql
CREATE TABLE agent_settings (
  agent TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-3 models
- file: `engine/limo/agents/models.py` (edit)
- do: add `model: str | None = None` to `Agent`; add `ModelIn(BaseModel)` with `model_config = ConfigDict(extra="forbid")` and `model: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")`. Pydantic warns on a field named `model` with the `model_` namespace only for `model_*` names; `model` alone is fine — if a warning appears, add `protected_namespaces=()` to that `ConfigDict`.
- verify: `cd engine && uv run python -c "from limo.agents.models import ModelIn; ModelIn(model='claude-haiku-5-5')"` → exit 0

### STEP-4 settings repo and agent service
- file: `engine/limo/agents/settings_repo.py`, `engine/limo/agents/agent_service.py` (create)
- do:
  - `AgentSettingsRepo(db_path)`: `get(agent) -> str | None`; `all() -> dict[str, str]`; `set(agent, model) -> None` using `INSERT INTO agent_settings (agent, model, updated_at) VALUES (?, ?, ?) ON CONFLICT(agent) DO UPDATE SET model = excluded.model, updated_at = excluded.updated_at`. One connection per method.
  - `AgentService(registry: AgentRegistry, settings: AgentSettingsRepo, default_model: str)`: `list() -> list[Agent]` = registry agents with `model` = `settings.all().get(name, default_model)` (use `agent.model_copy(update={"model": …})`); `model_for(agent) -> str` = `settings.get(agent) or default_model`; `set_model(name, model) -> Agent`: name not in `AGENT_NAMES` → `NotFound("agent_not_found", f"agent {name} not found")`; save; return that agent from `list()`.
- verify: `cd engine && uv run python -c "import limo.agents.agent_service"` → exit 0

### STEP-5 routes
- file: `engine/limo/api/agents_routes.py` (edit)
- do: `agents_router(service: AgentService)`; `GET ""` → `service.list()`; add `PUT "/{name}/model"` (`response_model=Agent`, body `ModelIn`) → `service.set_model(name, body.model)`
- verify: `cd engine && uv run python -c "import limo.api.agents_routes"` → exit 0

### STEP-6 runs use the agent's model
- file: `engine/limo/agents/service.py` (edit)
- do: add `agent_settings: AgentSettingsRepo` to `RunStores`; in `start`, `model = self._stores.agent_settings.get(data.agent) or self._config.model` and use it for the `Run`. No other change.
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-7 wiring
- file: `engine/limo/app.py` (edit)
- do: create `agent_settings = AgentSettingsRepo(settings.db_path)`; pass it in `RunStores(…, agent_settings)`; `app.include_router(agents_router(AgentService(AgentRegistry(settings.skills_dir), agent_settings, settings.default_model)))`
- verify: `mise run test:engine` → all pass (28 earlier + 7 new = 35)

### STEP-8 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 35 passed

### STEP-9 error assertions read the error envelope (revision 1: verify r0)
- file: `engine/tests/functional/test_agent_settings.py` (edit)
- do: replace every `r.json()["code"]` with `r.json()["error"]["code"]` (FT-3.3 and FT-3.4); change nothing else
- verify: `mise run test:engine` → 35 passed

### STEP-10 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 35 passed

## Do not
- change the runs API body, tools, allowlists, or prompts
- add price, cost, or budget fields
- add `# noqa` anywhere

## Doc updates
- context/data.md: Main entities — `agent_settings` (agent PK, model, updated_at) — `003_agent_settings.sql`; `settings` line: model per agent now lives in `agent_settings`
- context/api.md: Reference implementations — agents: `engine/limo/api/agents_routes.py` (`GET /api/agents`, `PUT /api/agents/{name}/model`)
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
