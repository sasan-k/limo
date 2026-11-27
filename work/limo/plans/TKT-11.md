---
ticket: TKT-11
feature: limo
scenarios: [SC-22, SC-23]
scope: [runner, persistence]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/runner.feature, DESIGN.md#Scheduler, context/INDEX.md, context/code-rules.md, context/data.md, context/testing.md, engine/limo/agents/repo.py (all SELECTs, insert, finish, set_status), engine/limo/agents/models.py, engine/limo/agents/service.py (start), engine/limo/runner/tickets.py (STATUS_LINE, TicketState), engine/limo/incidents/detect.py (trigger_for), engine/limo/vcs/git.py, engine/limo/app.py (create_app), runs schema from a migrated db]
---
# TKT-11: Interrupted runs recover after a restart

## Design
- where: migration `013_runs_interrupted.sql` (rebuild `runs` to allow status `interrupted`, add `attempt`); `agents/` (Run status + attempt); `vcs/git.py` (`reset_workspace`); new `runner/recovery.py` called once in `create_app`; `runner/tickets.py` parses tries; `incidents/detect.py` adds trigger `limits`
- responsibilities:
  - `RecoveryService.recover()` — every run still `queued`/`running` in the db becomes `interrupted` (error `interrupted by restart`, `finished_at` set); each affected project's workspace is reset with `git reset --hard HEAD` and `git clean -fd -e work`; failures are logged and skipped (startup never fails)
  - `RunService.start` — `attempt` = 1 + number of earlier runs with the same project, feature, ticket and agent
  - `TicketState` — gains `build_tries`, `plan_tries` (parsed from `fx status`)
  - `trigger_for` — latest non-resolver run `interrupted` and agent `build` with `build_tries >= 2` → `("limits", run.id)`; any other interrupted run → no trigger (the runner simply dispatches the stage again)
- reuse: `GitOps._git`, `RunRepo`, `ProjectRepo`, incidents flow from TKT-9/10
- contracts:
  - `Run.status`: `queued | running | succeeded | failed | interrupted`; `Run.attempt: int` (1-based)
  - `RunRepo.finish` keeps its guard (`queued`/`running` only), so a worker that finishes after a restart cannot overwrite `interrupted`
  - recovery runs in `create_app` right after `migrate`, before the app serves requests
- data: `runs` rebuilt with `CHECK (status IN ('queued','running','succeeded','failed','interrupted'))` and `attempt INTEGER NOT NULL DEFAULT 1`; existing rows and indexes kept
- decisions: follows DESIGN.md › Scheduler (on start: running → interrupted, reset workspace, retry within limits), ADR-3, ADR-10 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a
- input validation: none (no new input)
- injection: git via argv; SQL parameterized
- data exposure / PII: `git clean -e work` keeps local `work/` files
- secrets: none
- rate limit / abuse: retry limits still apply (`limits` trigger)
- audit: interrupted runs keep their row with error `interrupted by restart`
### Performance
- queries (N+1, indexes): one query for active runs; attempt count via index `runs_project_feature_agent`
- pagination / limits: n/a
- payload size: n/a
- caching: n/a
- external calls (timeouts/retries): git via executor timeout
- sync vs async: recovery is synchronous at startup (few runs)
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 recover on startup | FT-11.1 | n/a: no input | n/a: none | n/a: one pass | FT-11.6 | FT-11.3 | FT-11.4 | FT-11.5 |
| OP-2 `limits` trigger for an interrupted build | FT-11.2 | n/a: tries from fx | n/a: ticket exists | n/a: one incident | n/a: any status | n/a: dedup per run id (TKT-9) | FT-11.1 | n/a: local |
| OP-3 attempt numbering | FT-11.1 | n/a: computed | n/a: none | n/a: computed | n/a: computed | n/a: computed | FT-11.7 | n/a: local |

## Functional tests
File `engine/tests/functional/test_recovery.py`. A "restart" = build a second app on the same settings: `TestClient(create_app(settings, Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=llm, host=host)))` (pattern: `tests/functional/test_runs.py:75-90`) and use it from then on. A blocking build: `llm.responder = blocking_build(settings.skills_dir, seconds=1.5)` (STEP-1: build requests sleep, every agent then answers `final()`). Helpers in `tests/builders.py`: `add_cart_project`, `set_status`, `write_workspace_file`. Step = `POST /api/projects/shop/features/cart/step` (read `r.json()["run"]["agent"]`, `["attempt"]`, `["id"]`); run = `GET /api/runs/{id}` (read `status`, `error`, `attempt`); incidents = `GET /api/projects/shop/features/cart/incidents`. Workspace = `settings.workspaces_dir / "shop"`; committed content via `git show HEAD:src/cart.py` (subprocess, cwd = workspace).

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-11.1 | SC-22, OP-1:happy, OP-3:happy, OP-2:boundary | `engine/tests/functional/test_recovery.py` | cart project; `set_status TKT-1 planned`; blocking build; POST step → build run (attempt 1) running; `write_workspace_file … "src/cart.py", "changed\n"` | restart; GET the first run; POST step on the new app | first run `status` "interrupted", `error` "interrupted by restart"; `src/cart.py` content == `git show HEAD:src/cart.py`; step starts `build` with `attempt` 2 |
| FT-11.2 | SC-23, OP-2:happy | `engine/tests/functional/test_recovery.py` | cart project; `fx set work/cart TKT-1 status=planned build_tries=2` (via `set_status` helper extended in STEP-1 to accept extra `key=value` pairs); blocking build; POST step → build running | restart; POST step | step does not start a `build` run; incidents has an item `ticket` "TKT-1", `trigger` "limits" |
| FT-11.3 | OP-1:idempotency | `engine/tests/functional/test_recovery.py` | FT-11.1 up to the first restart | restart again | the first run is still "interrupted"; no error |
| FT-11.4 | OP-1:boundary | `engine/tests/functional/test_recovery.py` | cart project, no runs; `write_workspace_file … "src/cart.py", "local edit\n"` | restart | `src/cart.py` still `local edit` (no reset without interrupted runs) |
| FT-11.5 | OP-1:external-failure | `engine/tests/functional/test_recovery.py` | FT-11.1 setup up to the running build; then `shutil.rmtree(workspace)` | restart | the new app starts (GET `/api/agents` → 200); the run is "interrupted" |
| FT-11.6 | OP-1:invalid-state | `engine/tests/functional/test_recovery.py` | FT-11.1 after restart; wait 2 s so the old worker finishes | GET the first run | still "interrupted" (late finish ignored) |
| FT-11.7 | OP-3:boundary | `engine/tests/functional/test_recovery.py` | cart project; `set_status TKT-1 planned`; `llm.responder = stage_responder(settings.skills_dir)` | POST step; `wait_run` | the build run's `attempt` is 1 |

## Context pack
- `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` — STEP-3 edit
- `engine/limo/runner/tickets.py` — STEP-4 edit
- `engine/limo/incidents/detect.py` — STEP-5 edit
- `engine/limo/vcs/git.py` — STEP-6 edit
- `engine/limo/projects/repo.py`, `engine/limo/projects/models.py`, `engine/limo/executor/ports.py` — read
- `engine/limo/app.py` — STEP-7 edit
- `engine/tests/builders.py`, `engine/tests/fakes/llm.py` — STEP-1 edit
- `engine/tests/conftest.py`, `engine/tests/functional/test_runs.py` — read

## Steps
### STEP-1 test helpers and tests (test first)
- file: `engine/tests/fakes/llm.py`, `engine/tests/builders.py` (edit), `engine/tests/functional/test_recovery.py` (create)
- do:
  - `blocking_build(skills_dir: Path, seconds: float) -> Callable[[LlmRequest], LlmResponse]`: if `request.system` is the build prompt → `time.sleep(seconds)`; always return `final()`
  - `set_status(settings, project, ticket, status, *extra: str)` appends `extra` (e.g. `"build_tries=2"`) to the `fx set` argv
  - write FT-11.1 … FT-11.7; names `test_ft_11_<k>_<behavior>`, docstring starts `"""FT-11.<k> `
- verify: `mise run test:engine -- -k ft_11` → FAIL (status is "running"/"failed", no `attempt`)

### STEP-2 rebuild runs
- file: `engine/limo/store/migrations/013_runs_interrupted.sql` (create)
```sql
PRAGMA foreign_keys = OFF;
CREATE TABLE runs_new (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  agent TEXT NOT NULL,
  feature TEXT NOT NULL,
  ticket TEXT,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'interrupted')),
  model TEXT NOT NULL,
  output TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT,
  args TEXT,
  ticket_status TEXT,
  note TEXT,
  attempt INTEGER NOT NULL DEFAULT 1
);
INSERT INTO runs_new (id, project_id, agent, feature, ticket, status, model, output, error, created_at,
  finished_at, args, ticket_status, note)
  SELECT id, project_id, agent, feature, ticket, status, model, output, error, created_at,
  finished_at, args, ticket_status, note FROM runs;
DROP TABLE runs;
ALTER TABLE runs_new RENAME TO runs;
CREATE INDEX runs_project_agent ON runs (project_id, agent);
CREATE INDEX runs_status ON runs (status);
CREATE INDEX runs_project_feature_agent ON runs (project_id, feature, agent);
PRAGMA foreign_keys = ON;
```
- verify: `mise run test:engine` → all earlier tests pass (152)

### STEP-3 runs: interrupted + attempt
- file: `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` (edit)
- do:
  - `RunStatus = Literal["queued", "running", "succeeded", "failed", "interrupted"]` in `models.py`; use it for `Run.status` and for the `status` params of `RunRepo.set_status` and `RunRepo.finish`; `Run.attempt: int = 1`
  - `RunRepo.insert` writes `attempt`; add `r.attempt` to the column list of each of the three `SELECT r.id, p.name AS project, …` queries (`get`, `latest`, `latest_for_ticket`)
  - `RunRepo.count_attempts(project_id, feature, ticket, agent) -> int` (`ticket IS ?`); `RunRepo.active_runs() -> list[tuple[str, str]]` (run id, project_id; status `queued`/`running`); `RunRepo.interrupt(run_id)` = `UPDATE runs SET status = 'interrupted', error = 'interrupted by restart', finished_at = ? WHERE id = ? AND status IN ('queued', 'running')`
  - `RunService.start`: `attempt = self._stores.runs.count_attempts(project.id, data.feature, data.ticket, data.agent) + 1`, set on the new `Run`
- verify: `mise run test:engine -- -k ft_11_7` → passed

### STEP-4 ticket tries on the board
- file: `engine/limo/runner/tickets.py` (edit)
- do: `TicketState` gains `build_tries: int = 0`, `plan_tries: int = 0`; `STATUS_LINE = re.compile(r"^(TKT-\d+): status=(\S+) build_tries=(\d+) plan_tries=(\d+)", re.M)`; build states with `int(...)` for both tries
- verify: `mise run test:engine -- -k "ft_5 or ft_9"` → passed

### STEP-5 limits trigger
- file: `engine/limo/incidents/detect.py` (edit)
- do: in `trigger_for`, right after the `blocked` check: `if latest is not None and latest.status == "interrupted": return ("limits", latest.id) if latest.agent == "build" and state.build_tries >= 2 else None`
- verify: `cd engine && uv run python -c "import limo.incidents.detect"` → exit 0

### STEP-6 workspace reset
- file: `engine/limo/vcs/git.py` (edit)
- do: `GitOps.reset_workspace(workspace: Path) -> None`: `reset --hard HEAD`, then `clean -fd -e work`; non-zero exit → `GitError`
- verify: `cd engine && uv run python -c "import limo.vcs.git"` → exit 0

### STEP-7 recovery at startup
- file: `engine/limo/runner/recovery.py` (create), `engine/limo/app.py` (edit)
- do: `RecoveryService(runs: RunRepo, projects: ProjectRepo, git: GitOps)` with `recover() -> int`: for each `(run_id, project_id)` in `active_runs()`: `interrupt(run_id)`; collect project ids; for each project (`ProjectRepo.get_by_id` — add it to `projects/repo.py` if missing: `SELECT * FROM projects WHERE id = ?`) whose workspace dir exists: `git.reset_workspace(Path(project.workspace))`, catching `GitError` and `OSError` with `logging.getLogger(__name__).warning(...)`; return the number of interrupted runs. In `create_app`, right after `migrate(settings.db_path)`: `RecoveryService(RunRepo(settings.db_path), ProjectRepo(settings.db_path), GitOps(deps.executor, settings.command_timeout_s)).recover()`
- also edit: `engine/limo/projects/repo.py` (add `get_by_id` if missing)
- verify: `mise run test:engine -- -k ft_11` → 7 passed

### STEP-8 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fix rounds), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

## Do not
- auto-start runs at startup (dispatch stays with the runner step / switch)
- change retry limits or the `fx` tries semantics
- add `# noqa`

## Doc updates
- context/INDEX.md: `runner` line — recovery at startup (interrupted runs, workspace reset)
- context/data.md: `runs` rebuilt (`013_runs_interrupted.sql`): status `interrupted`, `attempt`
- context/testing.md: `blocking_build`; restart = second `create_app` on the same settings
- context/glossary.md: Interrupted — a run cut off by a restart; its stage is dispatched again within limits — `interrupted`
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
