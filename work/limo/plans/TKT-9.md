---
ticket: TKT-9
feature: limo
scenarios: [SC-32, SC-33]
scope: [runner, agents]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/resolver.feature, skills/resolver/SKILL.md, skills/resolver/templates/resolve-report.md, DESIGN.md#Orchestration, context/INDEX.md, context/code-rules.md, context/security.md, context/testing.md, context/data.md, engine/limo/runner/service.py, engine/limo/runner/tickets.py, engine/limo/agents/repo.py, engine/limo/agents/models.py, engine/limo/agents/service.py, engine/tests/fakes/llm.py, engine/tests/builders.py]
---
# TKT-9: Stuck tickets open an incident, get a resolver run, and a retry is applied

## Design
- where: new `limo/incidents/` (models, repo, detection, bundle, action parsing, service); runs gain `ticket_status`; `RunRepo.finish` only finishes active runs; runner step sweeps timeouts first and handles incidents before dispatch; `api/incidents_routes.py`; migration `010_incidents.sql`
- responsibilities:
  - `IncidentService.sweep_timeouts(project)` — runs of the project still `queued`/`running` and older than `settings.run_timeout_s` → `failed` with error `timeout`
  - `IncidentService.handle(project, feature, states) -> StepResult | None` — 1) apply the action of an open incident whose resolver run finished; 2) else open an incident for the first stuck ticket (map order) and start the resolver run; `None` = nothing to do
  - `IncidentService.open_tickets(project_id, feature) -> set[str]` — tickets with an incident in `open` or `needs_human` (the runner skips them)
  - parsing: the resolver run's `output`; the action is the JSON object in the last ```` ```json ```` block
- reuse: `RunService.start/latest`, `TicketBoard.set_status(TicketRef, status)`, `StepResult`, error classes, repo pattern
- contracts:
  - triggers per ticket (first match wins; tickets with an `open`/`needs_human` incident are skipped):
    - `question` — `work/<f>/questions.md` has a `## Q-<n> [open]` section whose `- blocks:` line contains the ticket id
    - `blocked` — ticket status `blocked`
    - `timeout` — the ticket's latest non-resolver run is `failed` with error `timeout`
    - `crash` — latest non-resolver run `failed` with an error not starting with `budget:` or `timeout`
    - `no-transition` — latest non-resolver run `succeeded` and its `ticket_status` equals the current status
    - the same trigger is not raised twice for the same run (incident stores `run_id`, null for question/blocked)
  - incident: `k` = 1 + incidents of that ticket; bundle `work/<f>/incidents/<ticket>-<k>.md` lines: `# Incident <ticket> #<k>`, `- trigger: <t>`, `- ticket status: <s>`, `- latest run: <agent> <status> <error or ->`; resolver run = `RunIn(agent="resolver", feature, ticket, args=f"incident={k}")`; step → `{"run": <resolver run>, "reason": "resolving"}`
  - applying (resolver run finished): run `failed` → incident `needs_human`; no parsable JSON / `type` not in `retry, answer, edit-ticket, replan, escalate` → `needs_human`; `retry` with `stage` in `{plan: todo, build: planned, verify: built, close: verified}` → set that ticket status, incident `resolved`; any other valid type → `needs_human` (handled in TKT-19); step → `{"run": null, "reason": "resolved" | "needs_human"}`
  - `GET /api/projects/{name}/features/{feature}/incidents` → 200 `[{"ticket", "k", "trigger", "status": "open"|"resolved"|"needs_human", "action": str | null, "run_id": str | null}]` ordered by creation · 404 `project_not_found`
  - step `reason` gains `"resolving"`, `"resolved"`, `"needs_human"`
  - the runner records `ticket_status` (the ticket's status when dispatched) on every stage run it starts
- data: `incidents(id, project_id, feature, ticket, k, trigger, status, run_id, resolver_run_id, action, created_at)`; `runs.ticket_status TEXT`
- decisions: follows DESIGN.md › Resolver (allowlisted JSON action, runner applies), ADR-4 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): the resolver only returns text; the runner validates the action against the allowlist before acting
- input validation: action JSON parsed with `json.loads`, type and stage checked against fixed sets; anything else → `needs_human`
- injection: no shell; fx via argv; SQL parameterized
- data exposure / PII: bundle holds statuses and run errors only
- secrets: none
- rate limit / abuse: one incident per ticket at a time; resolver runs count as runs (one active at a time)
- audit: `incidents` rows with action text
### Performance
- queries (N+1, indexes): open incidents of a feature in one query; index `incidents(project_id, feature, status)`; latest run per ticket via index `runs(project_id, feature, agent)` plus a `ticket` filter
- pagination / limits: n/a
- payload size: bundle ≤ 10 lines
- caching: n/a
- external calls (timeouts/retries): none added
- sync vs async: detection in the step; resolver runs in the worker
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 detect + open incident (step) | FT-9.1 | n/a: triggers come from local state | n/a: project/feature checked by step | FT-9.5 | n/a: every status can be stuck | FT-9.5 | FT-9.6 | n/a: no external call |
| OP-2 apply resolver action (step) | FT-9.2 | FT-9.3 | n/a: incident exists | n/a: one action per incident | FT-9.4 | n/a: applied once, incident leaves `open` | n/a: single action | FT-9.7 |
| OP-3 list incidents `GET …/incidents` | FT-9.2 | n/a: path checked | FT-9.8 | n/a: read only | n/a: read only | n/a: read only | FT-9.9 | n/a: no external call |
| OP-4 timeout sweep | FT-9.1 | n/a: no input | n/a: none | n/a: conditional update | FT-9.10 | n/a: only active runs change | n/a: one cutoff | n/a: local |

## Functional tests
File: `engine/tests/functional/test_incidents.py`. Step = `POST /api/projects/shop/features/cart/step` → read `r.json()["reason"]`, `r.json()["run"]["agent"]`, `r.json()["run"]["args"]`; incidents = `GET /api/projects/shop/features/cart/incidents` → list of dicts. Wait for runs with `wait_run(client, run_id)` (`tests/builders.py`). `set_status`, `get_status`, `write_workspace_file`, `add_cart_project` are in `tests/builders.py`. Fake responders (STEP-1, `tests/fakes/llm.py`): `resolver_responder(skills_dir, action_text)` answers resolver requests with `final(action_text)` and every other agent with `final()`.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-9.1 | SC-32, OP-1:happy, OP-4:happy | `engine/tests/functional/test_incidents.py` | parametrize trigger: `blocked` (`set_status TKT-1 blocked`); `no-transition` (step → plan run, wait; fake answers `final()` so status stays todo); `crash` (`llm.fail_with = LlmError("x")`; step; wait; `llm.fail_with = None`); `timeout` (own client with `Settings(…, run_timeout_s=0.2)`; `llm.responder` sleeps 0.5 s then `final()`; step; `time.sleep(0.3)`); `question` (`write_workspace_file … "work/cart/questions.md", "## Q-3 [open] Which currency?\n- blocks: TKT-1\n"`) | POST step | `reason` "resolving"; `run.agent` "resolver", `run.args` "incident=1"; incidents == one item with `ticket` "TKT-1", `trigger` == the parameter, `status` "open"; workspace file `work/cart/incidents/TKT-1-1.md` exists and contains `- trigger: <parameter>` |
| FT-9.2 | SC-33, OP-2:happy, OP-3:happy | `engine/tests/functional/test_incidents.py` | `set_status TKT-1 blocked`; `llm.responder = resolver_responder(skills_dir, "```json\n{\"type\": \"retry\", \"stage\": \"build\"}\n```")`; step → resolver run; wait | POST step; then POST step | 1st: `reason` "resolved"; TKT-1 status "planned"; incident `status` "resolved", `action` contains `"retry"`; 2nd: `run.agent` "build" |
| FT-9.3 | OP-2:validation | `engine/tests/functional/test_incidents.py` | as FT-9.2 but the resolver answers `"no json here"`; and in a second parametrized case `"```json\n{\"type\": \"merge\"}\n```"` | POST step after the resolver run | `reason` "needs_human"; incident `status` "needs_human"; TKT-1 still "blocked" |
| FT-9.4 | OP-2:invalid-state | `engine/tests/functional/test_incidents.py` | as FT-9.2 but the action is `{"type": "answer", "question": "Q-3", "answer": "EUR", "source": "x"}` | POST step | `reason` "needs_human" (answer is handled in TKT-19) |
| FT-9.5 | OP-1:conflict, OP-1:idempotency | `engine/tests/functional/test_incidents.py` | FT-9.3 state (incident `needs_human`) | POST step twice | incidents still has exactly 1 item; no new resolver run started (`reason` not "resolving") |
| FT-9.6 | OP-1:boundary | `engine/tests/functional/test_incidents.py` | `set_status TKT-1 blocked`, `set_status TKT-3 blocked` | POST step | one incident, for `TKT-1` |
| FT-9.7 | OP-2:external-failure | `engine/tests/functional/test_incidents.py` | `set_status TKT-1 blocked`; step → resolver run; `llm.fail_with = LlmError("down")` set before that step so the resolver run fails; wait | POST step | `reason` "needs_human" |
| FT-9.8 | OP-3:not-found | `engine/tests/functional/test_incidents.py` | — | GET `/api/projects/nope/features/cart/incidents` | 404 `project_not_found` |
| FT-9.9 | OP-3:boundary | `engine/tests/functional/test_incidents.py` | cart project, nothing stuck | GET incidents | `[]` |
| FT-9.10 | OP-4:invalid-state | `engine/tests/functional/test_incidents.py` | timeout case of FT-9.1, then `time.sleep(0.4)` so the slow worker returns | GET the timed-out run (`/api/runs/{id}`) | `status` "failed", `error` "timeout" (the late worker did not overwrite it) |

## Context pack
- `engine/limo/runner/service.py`, `engine/limo/runner/models.py`, `engine/limo/runner/tickets.py` — STEP-7 edit / read
- `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` — STEP-3 edit
- `engine/limo/config.py` — STEP-3 edit
- `engine/limo/api/runner_routes.py` — like: router factory
- `engine/limo/app.py` — STEP-8 edit
- `engine/limo/common/errors.py`, `engine/limo/store/db.py`, `engine/limo/projects/models.py`, `engine/limo/features/repo.py` — read
- `engine/tests/fakes/llm.py` — STEP-1 edit; `engine/tests/builders.py`, `engine/tests/conftest.py` — read
- `engine/tests/functional/test_runs.py`:75-90 — like: building an own client with custom `Settings`

## Steps
### STEP-1 fake resolver responder and tests (test first)
- file: `engine/tests/fakes/llm.py` (edit), `engine/tests/functional/test_incidents.py` (create)
- do: add to the fake module:
```python
def resolver_responder(skills_dir: Path, action_text: str) -> Callable[[LlmRequest], LlmResponse]:
    """Resolver requests get `final(action_text)`; every other agent ends at once with `final()`."""
    resolver_prompt = (skills_dir / "resolver" / "SKILL.md").read_text()

    def respond(request: LlmRequest) -> LlmResponse:
        return final(action_text) if request.system == resolver_prompt else final()

    return respond
```
  Then write FT-9.1 … FT-9.10 (FT-9.1 and FT-9.3 parametrized); names `test_ft_9_<k>_<behavior>`, docstring starts `"""FT-9.<k> `.
- verify: `mise run test:engine -- -k ft_9` → FAIL (404 on `/incidents`)

### STEP-2 tables
- file: `engine/limo/store/migrations/010_incidents.sql` (create)
```sql
CREATE TABLE incidents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  k INTEGER NOT NULL,
  trigger TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'needs_human')),
  run_id TEXT,
  resolver_run_id TEXT,
  action TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX incidents_feature ON incidents (project_id, feature, status);
ALTER TABLE runs ADD COLUMN ticket_status TEXT;
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-3 runs: ticket_status, guarded finish, ticket queries, timeout setting
- file: `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py`, `engine/limo/config.py` (edit)
- do: `RunIn.ticket_status: str | None = Field(default=None, pattern=r"^[a-z]+$")`, `Run.ticket_status: str | None = None`; insert/read it. `RunRepo.finish` SQL gets `AND status IN ('queued', 'running')`. Add `RunRepo.latest_for_ticket(project_id, feature, ticket) -> Run | None` (newest run with `agent != 'resolver'`) and `RunRepo.active_older_than(project_id, cutoff_iso) -> list[str]` (ids). `RunService` exposes `latest_for_ticket`, `fail_timed_out(project_id, cutoff_iso) -> int` (finish each id as `failed`, error `timeout`), `get`. Settings: `run_timeout_s: float = 1800.0`.
- verify: `mise run test:engine` → 107 passed

### STEP-4 incidents repo and parsing
- file: `engine/limo/incidents/__init__.py` (empty), `models.py`, `repo.py`, `actions.py` (create)
- do:
  - models: `Incident(BaseModel)` (`ticket, k: int, trigger, status, action: str | None, run_id: str | None`) + internal frozen dataclass `IncidentRow` (adds `id`, `resolver_run_id`)
  - repo `IncidentRepo(db_path)`: `add(project_id, feature, row: IncidentRow)`; `list(project_id, feature) -> list[IncidentRow]`; `open_for(project_id, feature) -> list[IncidentRow]` (status `open`); `blocking_tickets(project_id, feature) -> set[str]` (status `open` or `needs_human`); `count_for(project_id, feature, ticket) -> int`; `exists_for_run(project_id, ticket, trigger, run_id) -> bool`; `set_resolver_run(id, run_id)`; `close(id, status, action)`
  - `actions.py`: `ALLOWED = {"retry", "answer", "edit-ticket", "replan", "escalate"}`; `RETRY_STATUS = {"plan": "todo", "build": "planned", "verify": "built", "close": "verified"}`; `parse_action(output: str | None) -> dict[str, Any] | None` = `json.loads` of the last match of ```` r"```json\s*(\{.*?\})\s*```" ```` (`re.S`), `None` on no match / bad JSON / missing or unknown `type`
- verify: `cd engine && uv run python -c "import limo.incidents.repo, limo.incidents.actions"` → exit 0

### STEP-5 detection and bundle
- file: `engine/limo/incidents/detect.py` (create)
- do: `blocking_questions(workspace, feature) -> dict[str, str]` (ticket → `Q-n` from `questions.md`: a line `## Q-<n> [open]…` starts a section; its `- blocks:` line lists ids via `re.findall(r"TKT-\d+", …)`); `trigger_for(state: TicketState, latest: Run | None, questions: dict[str, str]) -> tuple[str, str | None] | None` returns `(trigger, run_id)` per Design › contracts; `write_bundle(workspace, feature, ticket, k, lines: list[str]) -> None`
- verify: `cd engine && uv run python -c "import limo.incidents.detect"` → exit 0

### STEP-6 incident service
- file: `engine/limo/incidents/service.py` (create), `engine/limo/runner/models.py` (edit)
- do:
  - `StepResult.reason` adds `"resolving"`, `"resolved"`, `"needs_human"`
  - `IncidentService(repo: IncidentRepo, runs: RunService, board: TicketBoard, timeout_s: float)`:
    - `sweep_timeouts(project)` → `runs.fail_timed_out(project.id, (now - timeout_s).isoformat())`
    - `open_tickets(project_id, feature)` → `repo.blocking_tickets`
    - `handle(project, feature, states) -> StepResult | None`: first `_apply_finished(...)` for each open incident whose resolver run is `succeeded`/`failed` (per Design › applying); then `_open_next(...)`: first state (map order) not in `blocking_tickets` with a trigger that `exists_for_run` has not seen → `k = count_for + 1`, write bundle, add row (`open`), start resolver run (`RunIn(agent="resolver", feature=feature, ticket=…, args=f"incident={k}")`), `set_resolver_run`, return `StepResult(run=…, reason="resolving")`
    - keep each method ≤ 40 lines
  - `GET` support: `list(project, feature) -> list[Incident]`
- verify: `cd engine && uv run python -c "import limo.incidents.service"` → exit 0

### STEP-7 runner hook
- file: `engine/limo/runner/service.py` (edit)
- do: `RunnerDeps` gains `incidents: IncidentService`. In `step`: right after the project lookup → `self._incidents.sweep_timeouts(project)`; after `self._issues.sync(...)` → `outcome = self._incidents.handle(project, feature, states)`; `if outcome is not None: return outcome`; add `self._incidents.open_tickets(project.id, feature)` to the `held` set; when starting a stage run pass `ticket_status=<that ticket's current status>` in `RunIn` (plan from `ready` → `"todo"`); add `incidents(project_name, feature) -> list[Incident]` (project lookup → service list)
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-8 route and wiring
- file: `engine/limo/api/incidents_routes.py` (create), `engine/limo/app.py` (edit)
- do: `incidents_router(runner: RunnerService)`: `GET /api/projects/{name}/features/{feature}/incidents` → `list[Incident]` (feature pattern as in runner routes). Wire `IncidentService(IncidentRepo(db), runs, board, settings.run_timeout_s)` into `RunnerDeps`; include the router
- verify: `mise run test:engine` → all pass (107 + FT-9 cases); earlier tests must pass unchanged

### STEP-9 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fixes), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

## Do not
- implement answer, edit-ticket, replan or escalate actions (TKT-19), resolve limits or labels (TKT-10), restart recovery (TKT-11)
- let the resolver run write files or call the host (its allowlist is unchanged)
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/incidents` (triggers, bundles, resolver run, retry action)
- context/layout.md: module list adds `incidents`
- context/api.md: incidents endpoint; step reasons `resolving`, `resolved`, `needs_human`
- context/data.md: `incidents`; `runs.ticket_status`; runs finish only while active
- context/testing.md: `resolver_responder`
- context/glossary.md: none (Incident, Trigger exist)
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
