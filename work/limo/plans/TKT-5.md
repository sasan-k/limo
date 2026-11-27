---
ticket: TKT-5
feature: limo
scenarios: [SC-14, SC-15, SC-16, SC-17, SC-18]
scope: [runner]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/runner.feature, work/limo/questions.md#Q-4, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, ADR-3:L2, ADR-4:L2, ADR-10:L2, ADR-11:L2, scripts/fx.py, engine/limo/agents/service.py, engine/limo/agents/tools.py, engine/limo/agents/repo.py, engine/limo/executor/*.py, engine/limo/app.py, engine/limo/config.py, engine/tests/builders.py, engine/tests/conftest.py, engine/tests/fakes/llm.py]
---
# TKT-5: The runner moves one ticket at a time through the stages

## Design
- where: new module `limo/runner/` (ticket board via `fx`, runner service); `api/runner_routes.py`; executor accepts extra env and puts `scripts/` on PATH; tools pass `FX_DB`/`FX_SCOPE` to commands; `scripts/fx.py` scopes ticket state per project
- responsibilities:
  - `scripts/fx` — symlink to `fx.py`, so `fx` is on the executor PATH without `install.sh`
  - `fx.py load_tickets` — when env `FX_SCOPE` is set, the DB key is `<scope>/<feature>` (two projects with the same feature name do not share state)
  - `LocalExecutor(path_prefix)` — prepends `path_prefix` to PATH; `run(..., env=None)` merges extra env
  - `ToolContext.env` — env for `run_command` (`FX_DB` = Limo db, `FX_SCOPE` = project name)
  - `limo.runner.tickets.TicketBoard` — reads ticket states for a feature by running `fx status` and `fx ready` through the executor; parses their output
  - `limo.runner.service.RunnerService.step(project, feature)` — starts at most one run: continue the in-progress ticket, else plan the first ready ticket; nothing while a run is active (`max_concurrent_tickets`)
- reuse: `RunService.start` (`agents/service.py`), `Executor` port, `ProjectRepo.get_by_name`, `fx status` / `fx ready` / `fx set` (single source of ticket state)
- contracts:
  - `POST /api/projects/{name}/features/{feature}/step` (feature `^[a-z0-9][a-z0-9-]{0,39}$`) → 200 `{"run": Run | null, "reason": "started" | "run_active" | "no_ready_ticket"}` · 404 `project_not_found` · 404 `feature_not_found` (no `work/<feature>/map.yaml` in the workspace) · 409 `map_invalid` (`fx status` exits non-zero) · 422 `validation_error`
  - dispatch: the first ticket in map order with status `verified` → close, `built` → verify, `planned` → build (in-progress tickets first); else the first id `fx ready` prints → plan; `review`, `blocked`, `done`, `abandoned` never start a run
  - concurrency: count of runs in `queued`/`running` across all projects ≥ `settings.max_concurrent_tickets` (default 1, Q-4) → `run_active`
  - `fx status` line format (parsed): `TKT-<n>: status=<s> build_tries=<b> plan_tries=<p>`; `fx ready` format: `ready: <ids separated by spaces | ->`
- data: no new table; ticket state stays in `tickets` owned by `fx`, now keyed `<project>/<feature>`
- decisions: follows ADR-3 (fx owns `tickets`), ADR-4, ADR-10 (commands via executor), ADR-11 (concurrency from settings) · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a: single local user
- input validation: feature path pattern; project lookup
- injection: `fx` called with argv lists; feature name validated before it reaches argv; `FX_SCOPE` is a validated project name
- data exposure / PII: none
- secrets: env passed to commands is only `PATH`, `HOME`, `FX_DB`, `FX_SCOPE` (no API keys, ADR-9)
- rate limit / abuse: one active run at a time
- audit: each started run is a `runs` row
### Performance
- queries (N+1, indexes): one `COUNT(*)` on `runs` by status per step; add index `runs(status)`
- pagination / limits: n/a
- payload size: n/a
- caching: n/a: none
- external calls (timeouts/retries): `fx` via executor with `command_timeout_s`
- sync vs async: `step` only starts a run (queued to the worker); returns immediately
- NFR targets: NFR-11 → concurrency read from `settings.max_concurrent_tickets`

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 runner step `POST /api/projects/{name}/features/{feature}/step` | FT-5.1 | FT-5.6 | FT-5.7 | FT-5.4 | FT-5.8 | n/a: a repeated step while a run is active starts nothing (FT-5.4) | FT-5.9, FT-5.10 | n/a: no external call (fx is local) |
| OP-2 agent `run_command` with fx env | FT-5.4 | n/a: argv validation covered by TKT-2 FT-2.12 | n/a: covered by TKT-2 | n/a: no unique resources | n/a: covered by TKT-2 | n/a: covered by TKT-2 | FT-5.10 | n/a: covered by TKT-2 FT-2.13 |

## Functional tests
All in `engine/tests/functional/test_runner.py`. Step responses are read as `r.json()["run"]["agent"]`, `r.json()["run"]["ticket"]`, `r.json()["reason"]`; errors as `r.json()["error"]["code"]`. Ticket status is set and read with the builder helpers from STEP-3 (they run the real `fx`).

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-5.1 | SC-14, OP-1:happy | `engine/tests/functional/test_runner.py` | cart project; `set_status(… "TKT-1", <status>)`; parametrize `(todo, plan), (planned, build), (built, verify), (verified, close)` | POST step for `cart` | 200, `reason` "started", `run.agent` == agent, `run.ticket` "TKT-1" |
| FT-5.2 | SC-15 | `engine/tests/functional/test_runner.py` | TKT-1 `blocked`, TKT-3 `done`, TKT-2 `todo` (depends on TKT-1) | POST step | `run` is null, `reason` "no_ready_ticket" |
| FT-5.3 | SC-16 | `engine/tests/functional/test_runner.py` | TKT-1 `review`, TKT-3 `done`, TKT-2 `todo` | POST step | `run` is null, `reason` "no_ready_ticket" |
| FT-5.4 | SC-17, OP-1:conflict, OP-2:happy | `engine/tests/functional/test_runner.py` | cart project; `llm.responder = stage_responder(skills_dir)` | loop: POST step; if started, a second POST step at once, then wait for the run; stop when `reason` is "no_ready_ticket" | every second POST gave `run_active`; started runs in order: `(plan, TKT-1), (build, TKT-1), (verify, TKT-1), (close, TKT-1), (plan, TKT-3), …`; `get_status(… "TKT-1")` == "review" |
| FT-5.5 | SC-18 | `engine/tests/functional/test_runner.py` | cart project; `stage_responder`; TKT-1 `todo` | step + wait twice (plan then build) | the build run's first LLM request has exactly 1 message (the task) |
| FT-5.6 | OP-1:validation | `engine/tests/functional/test_runner.py` | cart project | POST step for feature `Bad!` | 422 `validation_error` |
| FT-5.7 | OP-1:not-found | `engine/tests/functional/test_runner.py` | cart project | POST step on project `nope`; POST step for feature `posts` | 404 `project_not_found`; 404 `feature_not_found` |
| FT-5.8 | OP-1:invalid-state | `engine/tests/functional/test_runner.py` | cart project whose `work/cart/map.yaml` was overwritten (via the `write_workspace_file` helper) with `feature: cart\ntickets:\n  - id: TKT-1\n    bogus: x\n` | POST step | 409 `map_invalid` |
| FT-5.9 | OP-1:boundary | `engine/tests/functional/test_runner.py` | all three tickets `done` | POST step | `run` null, `reason` "no_ready_ticket" |
| FT-5.10 | OP-1:boundary, OP-2:boundary | `engine/tests/functional/test_runner.py` | projects `shop` and `blog` both with feature `cart` (same map); `set_status(shop, "TKT-1", "review")` | `get_status(blog, "TKT-1")`; POST step on `blog` | blog TKT-1 is "todo"; blog step starts `(plan, TKT-1)` |

## Context pack
- `scripts/fx.py`:82-91 — STEP-1 edit (`load_tickets`)
- `engine/limo/executor/ports.py`, `engine/limo/executor/local.py` — STEP-2 edit
- `engine/limo/agents/tools.py`:50-70, 200-220 — STEP-5 edit (`ToolContext`, `_run_command`)
- `engine/limo/agents/service.py` — STEP-5, STEP-6 edit
- `engine/limo/agents/repo.py` — STEP-6 edit (`active_count`)
- `engine/limo/agents/models.py` — read (`Run`, `RunIn`)
- `engine/limo/projects/repo.py` — read
- `engine/limo/common/errors.py` — read
- `engine/limo/config.py` — STEP-4 edit
- `engine/limo/app.py` — STEP-9 edit
- `engine/limo/api/cost_routes.py` — like: router factory with path patterns
- `engine/tests/conftest.py`, `engine/tests/builders.py`, `engine/tests/fakes/llm.py` — STEP-3 edit
- `engine/tests/functional/test_runs.py`:75-90 — STEP-3 edit (its own `LocalExecutor()`)

## Steps
### STEP-1 fx: scope and wrapper
- file: `scripts/fx.py` (edit), `scripts/fx` (create symlink)
- do: in `load_tickets`, right after `feature, tickets = load_map(work)`, add `scope = os.environ.get("FX_SCOPE")` and `if scope: feature = f"{scope}/{feature}"`. Create the symlink: `cd scripts && ln -s fx.py fx`.
- verify: `scripts/fx --help 2>&1 | head -1` → `ERROR: Factory helper: deterministic checks and status flips. Stdlib only.`

### STEP-2 executor env and PATH prefix
- file: `engine/limo/executor/ports.py`, `engine/limo/executor/local.py` (edit)
- do: port: `run(self, argv, cwd, timeout_s, env: Mapping[str, str] | None = None)`. `LocalExecutor.__init__(self, path_prefix: Path | None = None)`; base env = `{"PATH": f"{path_prefix}{os.pathsep}{PATH}" if path_prefix else PATH, "HOME": HOME}`; merged with `env` when given (`{**base, **(env or {})}`).
- verify: `cd engine && uv run python -c "from pathlib import Path; from limo.executor.local import LocalExecutor; r=LocalExecutor(Path('../scripts').resolve()).run(['fx','--help'], Path('.'), 30); print(r.code)"` → `2`

### STEP-3 test helpers (test first)
- file: `engine/tests/builders.py`, `engine/tests/fakes/llm.py`, `engine/tests/conftest.py`, `engine/tests/functional/test_runs.py` (edit)
- do:
  - conftest + test_runs.py: every `LocalExecutor()` becomes `LocalExecutor(path_prefix=settings.scripts_dir)` (needs STEP-4 field)
  - builders: `CART_MAP` constant:
```yaml
feature: cart
tickets:
  - id: TKT-1
    title: Cart shows a total
    scope: [api]
    scenarios: [SC-1]
    depends_on: []
  - id: TKT-2
    title: Cart total includes tax
    scope: [api]
    scenarios: [SC-2]
    depends_on: [TKT-1]
  - id: TKT-3
    title: Cart can be emptied
    scope: [api]
    scenarios: [SC-3]
    depends_on: []
```
    add `"work/cart/map.yaml": CART_MAP` and `"work/cart/plans/TKT-3.md": CART_PLAN` (Build needs a plan for every ticket it runs) to the files of `add_cart_project`; give `add_cart_project` an optional `name: str = "shop"` (repo + project name) and `start_and_wait` an optional `project: str = "shop"`
  - builders: `fx_env(settings, project) -> dict[str, str]` = `os.environ` copy + `PATH` prefixed with `settings.scripts_dir`, `FX_DB` = `settings.db_path`, `FX_SCOPE` = project; `set_status(settings, project, ticket, status)` runs `["fx", "set", "work/cart", ticket, f"status={status}"]` with `cwd=settings.workspaces_dir / project`, that env, `check=True`; `get_status(settings, project, ticket) -> str` runs `["fx", "status", "work/cart", ticket]` and returns the value after `status=`; `write_workspace_file(settings, project, rel, text)` writes a file in the workspace
  - fakes/llm.py: `FakeLlm.responder: Callable[[LlmRequest], LlmResponse] | None = None`, used before `script`; and
```python
NEXT_STATUS = {"plan": "planned", "build": "built", "verify": "verified", "close": "review"}


def stage_responder(skills_dir: Path) -> Callable[[LlmRequest], LlmResponse]:
    """Acts like each stage agent: first call sets the ticket's next status via fx, second call ends the run."""
    agents = {(skills_dir / a / "SKILL.md").read_text(): a for a in NEXT_STATUS}

    def respond(request: LlmRequest) -> LlmResponse:
        if len(request.messages) > 1:
            return final()
        agent = agents[request.system]
        fields = dict(part.split("=", 1) for part in request.messages[0]["content"].split())
        argv = ["fx", "set", f"work/{fields['feature']}", fields["ticket"], f"status={NEXT_STATUS[agent]}"]
        return tool_use("run_command", {"argv": argv})

    return respond
```
- verify: none until STEP-4/STEP-9 (settings field and route missing)

### STEP-4 settings
- file: `engine/limo/config.py` (edit)
- do: add `scripts_dir: Path = REPO_ROOT / "scripts"` and `max_concurrent_tickets: int = 1`
- verify: `cd engine && uv run python -c "from limo.config import Settings; print(Settings(_env_file=None).scripts_dir.name)"` → `scripts`

### STEP-5 commands get fx env
- file: `engine/limo/agents/tools.py`, `engine/limo/agents/service.py` (edit)
- do: `ToolContext` gains `env: dict[str, str]` (last field); `_run_command` passes `env=ctx.env` to `executor.run`. `RunConfig` gains `fx_db: Path`; `_run` builds the context with `env={"FX_DB": str(self._config.fx_db), "FX_SCOPE": project.name}`.
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-6 active run count
- file: `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` (edit), `engine/limo/store/migrations/005_runs_status_index.sql` (create)
- do: `RunRepo.active_count() -> int` = `SELECT COUNT(*) FROM runs WHERE status IN ('queued', 'running')`; `RunService.active_count()` returns it. Migration: `CREATE INDEX runs_status ON runs (status);`
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-7 ticket board
- file: `engine/limo/runner/__init__.py` (empty), `engine/limo/runner/tickets.py` (create)
- do: `@dataclass(frozen=True) TicketState(id: str, status: str)`; `class TicketBoard(executor: Executor, fx_db: Path, timeout_s: float)`:
  - `read(workspace: Path, project: str, feature: str) -> tuple[list[TicketState], list[str]]`: `work/<feature>/map.yaml` missing → `NotFound("feature_not_found", …)`; run `["fx", "status", f"work/{feature}"]` and `["fx", "ready", f"work/{feature}"]` in `workspace` with env `{"FX_DB": str(fx_db), "FX_SCOPE": project}`; any exit code ≠ 0 or `ExecutorError` → `Conflict("map_invalid", "<first line of stderr>")`
  - parse status lines with `^(TKT-\d+): status=(\S+)`; ready line `ready: …` → ids, `-` → `[]`
- verify: `cd engine && uv run python -c "import limo.runner.tickets"` → exit 0

### STEP-8 runner service
- file: `engine/limo/runner/models.py`, `engine/limo/runner/service.py` (create)
- do:
  - models: `StepResult(BaseModel)`: `run: Run | None`, `reason: Literal["started", "run_active", "no_ready_ticket"]`
  - `RunnerService(runs: RunService, projects: ProjectRepo, board: TicketBoard, max_concurrent: int)` with `step(project_name, feature) -> StepResult`:
    1. project missing → `NotFound("project_not_found", …)`
    2. `runs.active_count() >= max_concurrent` → `StepResult(run=None, reason="run_active")`
    3. `states, ready = board.read(Path(project.workspace), project.name, feature)`
    4. first state whose status is in `NEXT_AGENT = {"verified": "close", "built": "verify", "planned": "build"}` (map order) → that agent; else `ready[0]` → `plan`; else `no_ready_ticket`
    5. `runs.start(project.name, RunIn(agent=…, feature=feature, ticket=…))` → `StepResult(run=…, reason="started")`
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-9 route and wiring
- file: `engine/limo/api/runner_routes.py` (create), `engine/limo/app.py` (edit)
- do: `runner_router(service: RunnerService)`: `POST /api/projects/{name}/features/{feature}/step` (`StepResult`; `feature: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]`). In `app.py`: default `Deps` executor `LocalExecutor(path_prefix=settings.scripts_dir)`; `RunConfig(…, fx_db=settings.db_path)`; `RunnerService(runs, ProjectRepo(db), TicketBoard(deps.executor, settings.db_path, settings.command_timeout_s), settings.max_concurrent_tickets)`; include the router.
- verify: `mise run test:engine` → 47 passed (runner tests come in STEP-10)

### STEP-10 runner tests
- file: `engine/tests/functional/test_runner.py` (create)
- do: one function per FT-5.1 … FT-5.10 per the table (FT-5.1 parametrized); names `test_ft_5_<k>_<behavior>`, docstring starts `"""FT-5.<k> `. FT-5.4 loop: at most 12 iterations; collect `(run["agent"], run["ticket"])` of started runs; use `start`-less waiting: poll `GET /api/runs/{id}` like `start_and_wait`. FT-5.10 adds `blog` with `add_cart_project(client, tmp_path, name="blog")`.
- verify: `mise run test:engine -- -k ft_5` → 13 passed

### STEP-11 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 60 passed

## Do not
- add an automatic loop, on/off switch, SSE, branches, merge requests, or incident handling (later tickets)
- write ticket state with SQL; only through `fx`
- pass API keys or host tokens in command env
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/runner` — dispatch by ticket status via `fx` → `agents` (call), `executor` (fx); planned list drops `runner`
- context/layout.md: module list adds `runner`; Where to put new things — none
- context/api.md: Reference implementations — runner step: `engine/limo/api/runner_routes.py`
- context/data.md: Ownership — `tickets` rows keyed `<project>/<feature>` via `FX_SCOPE`; `runs_status` index
- context/security.md: Agent tools — command env is `PATH`, `HOME`, `FX_DB`, `FX_SCOPE` only
- context/testing.md: builders `set_status`, `get_status`, `write_workspace_file`, `fx_env`; fake `stage_responder`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
