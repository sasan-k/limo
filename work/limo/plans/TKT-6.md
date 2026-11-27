---
ticket: TKT-6
feature: limo
scenarios: [SC-19, SC-20, SC-21, SC-49, SC-59]
scope: [runner, api, host]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/runner.feature, work/limo/questions.md#Q-2#Q-10, DESIGN.md#Orchestration, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, ADR-3:L2, ADR-6:L2, engine/limo/runner/service.py, engine/limo/runner/tickets.py, engine/limo/agents/repo.py, engine/limo/agents/service.py, engine/limo/agents/models.py, engine/limo/projects/service.py, skills/architecture/SKILL.md (modes)]
---
# TKT-6: An intake form starts a feature locally; architecture and spec run before tickets

## Design
- where: new `limo/features/` (intake, feature phases); `runner/service.py` runs pre-ticket phases first; runs gain `args`; `projects/service.py` excludes `work/` from git; `api/features_routes.py`; migration `008_features.sql`
- responsibilities:
  - `limo.features.service.FeatureService` — intake: save requirements to the workspace, create the feature with its first phase; list features
  - `limo.features.phases.PhaseService.next_action(project, feature) -> PhaseAction` — decides the pre-ticket step from the feature's phase and the latest run of that phase; advances the phase
  - `RunnerService.step` — a feature with a phase other than `tickets` runs its phase action instead of ticket dispatch; features without a row (older tests) behave as `tickets`
  - `ProjectService.add` — appends `work/` to `<workspace>/.git/info/exclude` (REQ-53)
  - `TicketBoard.map_check(…) -> bool` — `fx map-check work/<feature>` exit code 0
- reuse: `RunService.start`, `RunRepo` (latest run query), `TicketBoard` env, repo pattern, error classes
- contracts:
  - `POST /api/projects/{name}/features` body `{"name": ^[a-z0-9][a-z0-9-]{0,39}$, "requirements": str 1..200000}` (`extra="forbid"`) → 201 `Feature` · 404 `project_not_found` · 409 `feature_exists` (row exists or `work/<name>/` exists in the workspace) · 422
  - `GET /api/projects/{name}/features` → 200 `[Feature]` ordered by `created_at`; `Feature` = `{"name", "phase": "architecture"|"spec"|"nfr"|"tickets", "created_at"}`
  - intake writes `work/<name>/requirements/<name>.md` = the requirements text; first phase = `architecture` when the workspace has no `context/` dir, else `spec`
  - `RunIn` / `Run` gain `args: str | None` (`^[a-z0-9][a-z0-9 =-]{0,79}$`); task text = `feature=<f>` + (` ticket=<t>` if ticket) + (` <args>` if args)
  - phase actions (each step; latest run = newest run of that project+feature+agent+args):
    - `architecture`: agent `architecture`, args `mode=init-existing`; no run → start; latest `failed` → `stage_failed`; `succeeded` → phase `spec`, continue
    - `spec`: agent `spec`, no args; no run → start; `failed` → `stage_failed`; `succeeded` → `map_check` false → 409 `map_invalid`; true → phase `nfr` if `work/<f>/nfr.md` has a line starting `| NFR-`, else `tickets`; continue
    - `nfr`: agent `architecture`, args `mode=nfr <feature>`; no run → start; `failed` → `stage_failed`; `succeeded` → phase `tickets`, continue
    - `tickets`: normal ticket dispatch (TKT-5/TKT-7)
  - step `reason` gains `"stage_failed"` (run null)
- data: `features(id, project_id, name, phase, created_at, UNIQUE(project_id, name))`; `runs.args TEXT` (nullable)
- decisions: follows ADR-3, ADR-6, Q-2 (intake in UI → local workspace), Q-10 (`work/` local, excluded from git) · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a
- input validation: name pattern; requirements 1–200,000 chars; `extra="forbid"`; args pattern
- injection: file path built only from the validated name inside the workspace; SQL parameterized
- data exposure / PII: requirements text stays in the local workspace, never committed (exclude + `:(exclude)work` pathspec)
- secrets: none
- rate limit / abuse: n/a
- audit: features row `created_at`; phase runs are `runs` rows
### Performance
- queries (N+1, indexes): latest-run lookup uses index `runs(project_id, feature, agent)`; one query per step
- pagination / limits: features list small
- payload size: requirements ≤ 200,000 chars
- caching: n/a: none
- external calls (timeouts/retries): `fx map-check` via executor timeout
- sync vs async: phase runs go to the worker like ticket runs
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 intake `POST /api/projects/{name}/features` | FT-6.1 | FT-6.6 | FT-6.7 | FT-6.8 | n/a: a new feature has no state | n/a: a repeat is a conflict (FT-6.8) | FT-6.12 | n/a: no external call |
| OP-2 step through pre-ticket phases | FT-6.2 | n/a: covered by TKT-5 FT-5.6 | n/a: covered by TKT-5 FT-5.7 | n/a: one active run covered by TKT-5 FT-5.4 | FT-6.11 | n/a: a running phase run blocks new ones (`run_active`) | FT-6.4, FT-6.9 | FT-6.10 |
| OP-3 list features `GET /api/projects/{name}/features` | FT-6.1 | n/a: no parameters | FT-6.7 | n/a: read only | n/a: read only | n/a: read only | FT-6.13 | n/a: no external call |
| OP-4 keep `work/` out of git | FT-6.5 | n/a: no input | n/a: workspace exists | n/a: append once | n/a: always | n/a: excluded on add | n/a: one pattern | n/a: no external call |

## Functional tests
All in `engine/tests/functional/test_features.py`. Paths: `F = "/api/projects/<project>/features"`, step = `POST /api/projects/<project>/features/<feature>/step` → `{"run", "reason"}`. Read `r.json()["phase"]`, `r.json()["run"]["agent"]`, `r.json()["run"]["args"]`, `r.json()["reason"]`, errors `r.json()["error"]["code"]`. Runs end via `wait_for_run(client, run_id)` (copy of the polling in `start_and_wait`; put it in `tests/builders.py` as `wait_run(client, run_id)`). A project with a `context/` dir: `add_cart_project` then `write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")`. A project without: `add_cart_project(client, tmp_path, name="blog")` (no `context/` in the fixture repo).

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-6.1 | SC-49, OP-1:happy, OP-3:happy | `engine/tests/functional/test_features.py` | shop with `context/` | POST `F` `{"name": "posts", "requirements": "Readers can comment on posts."}` | 201, `phase` "spec"; workspace file `work/posts/requirements/posts.md` == the text; GET `F` lists `posts` |
| FT-6.2 | SC-19, OP-2:happy | `engine/tests/functional/test_features.py` | blog (no `context/`); intake `posts` | POST step for `posts` | `phase` of intake was "architecture"; step starts `agent` "architecture", `args` "mode=init-existing"; fake LLM's first request task == `feature=posts mode=init-existing`; no run with agent `spec` exists yet (GET features shows phase "architecture") |
| FT-6.3 | SC-20 | `engine/tests/functional/test_features.py` | shop with `context/`; intake `posts`; step → spec run; wait; then write `work/posts/map.yaml` (one ticket TKT-1, scenario SC-1), `work/posts/features/a.feature` (`@SC-1 @REQ-1` scenario) and `work/posts/nfr.md` with a row `\| NFR-1 \| REQ-1 \| performance \| x \| y \| pending \|` | POST step | starts `architecture` with `args` "mode=nfr posts"; feature phase "nfr" |
| FT-6.4 | SC-21, OP-2:boundary | `engine/tests/functional/test_features.py` | as FT-6.3 but `nfr.md` has the header row only | POST step | starts `plan` for `TKT-1`; feature phase "tickets" |
| FT-6.5 | SC-59, OP-4:happy | `engine/tests/functional/test_features.py` | shop; `host` fake; intake `posts` (phase spec is fine); `drive_to_review` for feature `cart`; POST cart step → "shipped" | — | workspace `git status --porcelain` has no line containing `work/`; `git -C shop.git ls-tree -r --name-only limo/cart/TKT-1` has no path starting `work/posts/`; `.git/info/exclude` of the workspace contains `work/` |
| FT-6.6 | OP-1:validation | `engine/tests/functional/test_features.py` | shop | POST `F` with name `Posts!`; with `"requirements": ""`; with an extra field `"x": 1` | 422 each |
| FT-6.7 | OP-1:not-found, OP-3:not-found | `engine/tests/functional/test_features.py` | — | POST and GET `/api/projects/nope/features` | 404 `project_not_found` each |
| FT-6.8 | OP-1:conflict | `engine/tests/functional/test_features.py` | shop; intake `posts` | POST `F` `posts` again; POST `F` `cart` (its `work/cart/` exists in the repo) | 409 `feature_exists` each |
| FT-6.9 | OP-2:boundary | `engine/tests/functional/test_features.py` | shop with `context/`; intake `posts` | POST step | starts `spec` (no architecture run) |
| FT-6.10 | OP-2:external-failure | `engine/tests/functional/test_features.py` | shop with `context/`; intake `posts`; `llm.fail_with = LlmError("down")`; step → spec run fails; wait | POST step | `run` null, `reason` "stage_failed" |
| FT-6.11 | OP-2:invalid-state | `engine/tests/functional/test_features.py` | as FT-6.3 but `map.yaml` contains `feature: posts\ntickets:\n  - id: TKT-1\n    bogus: x\n` | POST step | 409 `map_invalid` |
| FT-6.12 | OP-1:boundary | `engine/tests/functional/test_features.py` | shop | POST `F` with requirements of 200,000 `a`; then name `big2` with 200,001 | 201; 422 |
| FT-6.13 | OP-3:boundary | `engine/tests/functional/test_features.py` | shop, no intake | GET `F` | `[]` |

## Context pack
- `engine/limo/runner/service.py`, `engine/limo/runner/models.py`, `engine/limo/runner/tickets.py` — STEP-7, STEP-8 edit
- `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` — STEP-4 edit
- `engine/limo/projects/service.py`, `engine/limo/projects/models.py`, `engine/limo/projects/repo.py` — STEP-5 edit / read
- `engine/limo/api/runner_routes.py` — like: router with path patterns
- `engine/limo/app.py` — STEP-9 edit
- `engine/limo/common/errors.py`, `engine/limo/store/db.py` — read
- `engine/tests/builders.py` — STEP-1 edit; `engine/tests/conftest.py`, `engine/tests/fakes/llm.py`, `engine/tests/fakes/host.py` — read

## Steps
### STEP-1 helper and tests (test first)
- file: `engine/tests/builders.py` (edit), `engine/tests/functional/test_features.py` (create)
- do: add `wait_run(client, run_id) -> dict[str, Any]` to builders (poll `GET /api/runs/{id}` until `succeeded`/`failed`, 5 s max; make `start_and_wait` use it). Write one test per FT-6.1 … FT-6.13; names `test_ft_6_<k>_<behavior>`, docstring starts `"""FT-6.<k> `. Git checks with `subprocess.run(["git", …], cwd=workspace, capture_output=True, text=True)`.
- verify: `mise run test:engine -- -k ft_6` → FAIL (404/405 on `/api/projects/shop/features`)

### STEP-2 tables
- file: `engine/limo/store/migrations/008_features.sql` (create)
```sql
CREATE TABLE features (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  phase TEXT NOT NULL CHECK (phase IN ('architecture', 'spec', 'nfr', 'tickets')),
  created_at TEXT NOT NULL,
  UNIQUE (project_id, name)
);
ALTER TABLE runs ADD COLUMN args TEXT;
CREATE INDEX runs_project_feature_agent ON runs (project_id, feature, agent);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-3 features module
- file: `engine/limo/features/__init__.py` (empty), `models.py`, `repo.py`, `service.py` (create)
- do:
  - models: `FeatureIn` (`extra="forbid"`; `name` pattern; `requirements: str = Field(min_length=1, max_length=200_000)`); `Feature` (`name`, `phase: Literal["architecture", "spec", "nfr", "tickets"]`, `created_at`)
  - repo `FeatureRepo(db_path)`: `add(project_id, feature: Feature)` (IntegrityError → `Conflict("feature_exists", …)`); `get(project_id, name) -> Feature | None`; `list(project_id) -> list[Feature]`; `set_phase(project_id, name, phase)`
  - service `FeatureService(features: FeatureRepo, projects: ProjectRepo)`: `create(project_name, data) -> Feature` — project missing → `NotFound("project_not_found", …)`; row exists or `<workspace>/work/<name>` exists → `Conflict("feature_exists", …)`; write `work/<name>/requirements/<name>.md`; phase `architecture` if `<workspace>/context` is not a dir else `spec`; `list(project_name)`
- verify: `cd engine && uv run python -c "import limo.features.service"` → exit 0

### STEP-4 runs carry args
- file: `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` (edit)
- do: `RunIn.args: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9 =-]{0,79}$")`; `Run.args: str | None = None`; repo `insert` writes `args`, `get` reads it; add `RunRepo.latest(project_id, feature, agent, args) -> Run | None` (newest by `created_at`, `args IS ?` comparison so `None` matches NULL); `RunService.start` copies `data.args`; `RunService.latest(project_id, feature, agent, args)`; task text per Design › contracts
- verify: `mise run test:engine` → all earlier tests still pass (87)

### STEP-5 keep work/ out of git
- file: `engine/limo/projects/service.py` (edit)
- do: after a successful clone, append `work/\n` to `<path>/.git/info/exclude` (create `info/` if missing; skip if the line is already there)
- verify: `mise run test:engine -- -k ft_1` → passed

### STEP-6 map-check on the board
- file: `engine/limo/runner/tickets.py` (edit)
- do: `TicketBoard.map_check(workspace, project, feature) -> bool` runs `["fx", "map-check", f"work/{feature}"]` with the same env as `read`; returns `code == 0` (`ExecutorError` → False)
- verify: `cd engine && uv run python -c "import limo.runner.tickets"` → exit 0

### STEP-7 phase service
- file: `engine/limo/features/phases.py` (create), `engine/limo/runner/models.py` (edit)
- do:
  - `StepResult.reason` adds `"stage_failed"`
  - `@dataclass(frozen=True) PhaseAction`: `run: RunIn | None`, `reason: Literal["start", "stage_failed", "tickets"]`
  - `PhaseService(features: FeatureRepo, runs: RunService, board: TicketBoard)`: `next_action(project: Project, feature: str) -> PhaseAction` — no row → `tickets`; loop over phases per Design › contracts (advance with `set_phase` and re-check, at most 3 times); `map_check` false → `Conflict("map_invalid", "fx map-check failed")`; NFR rows = any line of `work/<f>/nfr.md` starting with `| NFR-`
  - keep `next_action` ≤ 40 lines: one private method per phase
- verify: `cd engine && uv run python -c "import limo.features.phases"` → exit 0

### STEP-8 runner uses phases
- file: `engine/limo/runner/service.py` (edit)
- do: `RunnerDeps` gains `phases: PhaseService`. In `step`, right after the `run_active` check: `action = phases.next_action(project, feature)`; `start` → `runs.start(project.name, action.run)` → `StepResult(run, "started")`; `stage_failed` → `StepResult(None, "stage_failed")`; `tickets` → continue with the existing board/ship/dispatch code (unchanged)
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-9 routes and wiring
- file: `engine/limo/api/features_routes.py` (create), `engine/limo/app.py` (edit)
- do: `features_router(service: FeatureService)`: `POST /api/projects/{name}/features` (201, `Feature`), `GET /api/projects/{name}/features` (`list[Feature]`). In `app.py`: `feature_repo = FeatureRepo(db)`; `FeatureService(feature_repo, ProjectRepo(db))`; `PhaseService(feature_repo, runs, board)` into `RunnerDeps`; include the router
- verify: `mise run test:engine` → 100 passed (87 + 13)

### STEP-10 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 100 passed

## Do not
- commit anything under `work/`; push `context/` changes outside a ticket branch
- change ticket dispatch, shipping or polling
- add UI or the runner on/off switch
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/features` (intake, phases architecture → spec → nfr → tickets)
- context/layout.md: module list adds `features`
- context/api.md: features endpoints; step reason `stage_failed`; run `args`
- context/data.md: `features`; `runs.args`
- context/security.md: Data — `work/` excluded via `.git/info/exclude` at project add
- context/glossary.md: Phase — a feature's pre-ticket stage: architecture, spec, nfr, tickets — `phase`
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
