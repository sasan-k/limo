---
ticket: TKT-7
feature: limo
scenarios: [SC-24, SC-25, SC-26, SC-27, SC-28, SC-29]
scope: [host, runner]
revision: 3  # human-approved after resolver escalation (TKT-7-resolve-2)
run: from-STEP-16
read: [work/limo/map.yaml, work/limo/features/host.feature, work/limo/questions.md#Q-13#Q-14, DESIGN.md#Orchestration, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, ADR-4:L2, ADR-9:L2, ADR-10:L2, ADR-12:L2, engine/limo/runner/*.py, engine/limo/app.py, engine/tests/builders.py, engine/tests/conftest.py, engine/tests/fakes/llm.py]
---
# TKT-7: Each ticket ships as an auto-merge merge request and finishes on merge

## Design
- where: new `limo/hosts/` (RepoHost port + unconfigured adapter + merge-request repo), `limo/vcs/git.py` (branch, commit, push via executor), `limo/runner/shipping.py` (ship + poll); `RunnerService.step` ships and checks out ticket branches; `api/runner_routes.py` gains poll; migration `007_merge_requests.sql`; test fake `tests/fakes/host.py`
- responsibilities:
  - `limo.hosts.ports` — `RepoHost` Protocol and its value types; `HostError`
  - `limo.hosts.unconfigured.UnconfiguredHost` — default until real adapters exist (TKT-18): every call raises `HostError("repo host adapter not configured")`
  - `limo.hosts.repo.MergeRequestRepo` — `merge_requests` table
  - `limo.vcs.git.GitOps` — `start_ticket` (checkout the ticket branch: local → remote → new from `origin/<base>`), `commit_and_push` (never commits `work/`)
  - `limo.runner.shipping.ShippingService` — `ship` (commit, push, open MR once, enable auto-merge) and `poll` (merged → `done`; new change requests → review report + `todo`)
  - `RunnerService.step` — 1) ship a `review` ticket that has no open MR or needs a push; 2) before starting any stage run, `git.start_ticket`
- reuse: `TicketBoard` (fx status/ready), `fx set` via executor (same env as `TicketBoard.read`), `Executor`, error classes, repo pattern, `stage_responder` fake
- contracts:
  - `POST /api/projects/{name}/features/{feature}/step` — `reason` gains `"shipped"` (`run` null)
  - `POST /api/projects/{name}/features/{feature}/poll` → 200 `{"merged": [ticket ids], "changes_requested": [ticket ids]}` · 404 `project_not_found` · 422 `validation_error` · 502 `host_error`
  - ship/step errors: host failure → 502 `host_error`; git failure → 502 `git_failed`; nothing is recorded when shipping fails (the next step retries)
  - branch name: `limo/<feature>/<ticket>`; base: the project's `default_branch`; MR title `"<ticket> (<feature>)"`
  - commits: `git add -A -- . ':(exclude)work'`, `git -c user.name=Limo -c user.email=limo@localhost commit -m "<ticket>: <feature>"` (exit 1 "nothing to commit" is fine), `git push -u origin <branch>`
  - poll per open MR: `merged` → MR state `merged`, `fx set … status=done`; `changes_requested` comments with id not yet seen → write `work/<feature>/reports/<ticket>-review-<k>.md` (k = existing review reports + 1; one `- <body>` line per comment), `fx set … status=todo`, MR `needs_push = 1`, remember last comment id; else nothing
  - RepoHost port (all raise `HostError` on failure):
    - `open_merge_request(project: HostProject, branch: str, base: str, title: str) -> MergeRequestRef`
    - `enable_auto_merge(project: HostProject, number: int) -> None`
    - `merge_request_status(project: HostProject, number: int) -> MrStatus`
    - `HostProject(name, git_url, kind)`, `MergeRequestRef(number, url)`, `ReviewComment(id: str, body: str)`, `MrStatus(state: "open"|"merged"|"closed", approved: bool, change_requests: list[ReviewComment])`
- data: `merge_requests(id, project_id, feature, ticket, number, url, branch, state, last_review_id, needs_push, created_at)`
- decisions: follows ADR-4 (port + fake at the external boundary), ADR-10 (git via executor), ADR-12 (no live host in tests), DESIGN "Merge = approval only" + Q-14 (Limo never merges) · no new ADR

## Quality
### Security
- authn: n/a: ADR-7 (host credentials arrive with TKT-18 adapters)
- authz (permission/ownership): Limo has no merge call in its port; merging is done by the host after a human approves (SC-25)
- input validation: feature path pattern; branch built only from validated feature + `TKT-\d+`
- injection: git/fx via argv lists; `--` not needed (no user-supplied refs beyond validated names)
- data exposure / PII: review comment bodies stored only in the workspace report file
- secrets: none handled here; `work/` never committed (REQ-53)
- rate limit / abuse: one ship per step; poll is explicit
- audit: `merge_requests` rows with `created_at`, state changes
### Performance
- queries (N+1, indexes): open MRs of a feature in one query; index `merge_requests(project_id, feature, state)`
- pagination / limits: n/a
- payload size: n/a
- caching: n/a: none
- external calls (timeouts/retries): host calls through the port (adapters set timeouts, TKT-18); git via executor timeout
- sync vs async: ship/poll run inside the step/poll request (git + host calls are short); agent runs stay in the worker
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 ship on step (`review` ticket) | FT-7.1 | n/a: no input beyond validated path | n/a: covered by TKT-5 FT-5.7 | FT-7.7 | n/a: only `review` tickets ship | FT-7.8 | n/a: one ticket per step | FT-7.9 |
| OP-2 poll `POST …/poll` | FT-7.3 | FT-7.10 | FT-7.11 | n/a: read + idempotent updates | FT-7.4 | FT-7.12 | FT-7.13 | FT-7.14 |
| OP-3 start ticket branch (stage dispatch) | FT-7.5 | n/a: names validated upstream | n/a: base comes from the project | n/a: branch reused, not recreated (FT-7.6) | n/a: any stage may start | FT-7.6 | n/a: one branch per ticket | n/a: git errors map to 502 like FT-7.9 |
| OP-4 auto-merge request | FT-7.2 | n/a: no input | n/a: MR just created | n/a: once per MR (FT-7.8) | n/a: only right after opening | FT-7.8 | n/a: single call | FT-7.9 |

## Functional tests
All in `engine/tests/functional/test_shipping.py`. Fixture `host` (STEP-2) is the `FakeHost`; the client is built with it. Helper `drive_to_review(client, llm, settings)` (STEP-2): `llm.responder = stage_responder(settings.skills_dir)`, then repeat `POST …/step` + wait for the started run, until `get_status(settings, "shop", "TKT-1") == "review"` (max 8 steps). Paths: `S = "/api/projects/shop/features/cart/step"`, `P = "/api/projects/shop/features/cart/poll"`. Read `r.json()["reason"]`, `r.json()["merged"]`, `r.json()["changes_requested"]`, errors `r.json()["error"]["code"]`. Remote checks use `git` on the bare repo `tmp_path / "shop.git"`.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-7.1 | SC-24, OP-1:happy | `engine/tests/functional/test_shipping.py` | cart project; `drive_to_review`; `write_workspace_file(… "src/cart.py", "def total() -> int:\n    return 1\n")` and `write_workspace_file(… "work/cart/reports/x.md", "local")` | POST `S` | `reason` "shipped"; `git -C shop.git show limo/cart/TKT-1:src/cart.py` contains `return 1`; `git -C shop.git ls-tree -r --name-only limo/cart/TKT-1` has no new `work/cart/reports/x.md`; `host.mrs[1]` has branch `limo/cart/TKT-1`, base `main`, state `open`; TKT-1 status "review" |
| FT-7.2 | SC-25, OP-4:happy | `engine/tests/functional/test_shipping.py` | as FT-7.1 shipped | — | `("enable_auto_merge", 1)` in `host.calls`; no call named `merge` in `host.calls` |
| FT-7.3 | SC-26, OP-2:happy | `engine/tests/functional/test_shipping.py` | shipped; `host.approve(1)`; `host.merge(1)` | POST `P` | `merged` == `["TKT-1"]`; TKT-1 status "done" |
| FT-7.4 | SC-27, OP-2:invalid-state | `engine/tests/functional/test_shipping.py` | shipped, not approved | POST `P` | `merged` == `[]`, `changes_requested` == `[]`; TKT-1 status "review" |
| FT-7.5 | SC-28, OP-3:happy | `engine/tests/functional/test_shipping.py` | FT-7.3 state (TKT-1 merged, done) | POST `S` | started run `plan` / `TKT-2`; workspace `git rev-parse --abbrev-ref HEAD` == `limo/cart/TKT-2`; `git merge-base --is-ancestor <sha of main in shop.git> HEAD` exits 0 |
| FT-7.6 | SC-29, OP-3:idempotency | `engine/tests/functional/test_shipping.py` | shipped; `host.request_changes(1, "rename total() to cart_total()")` | POST `P`; then POST `S` | poll `changes_requested` == `["TKT-1"]`; `work/cart/reports/TKT-1-review-1.md` in the workspace contains `rename total() to cart_total()`; TKT-1 status "todo"; step starts `plan` / `TKT-1`; workspace branch is still `limo/cart/TKT-1` |
| FT-7.7 | OP-1:conflict | `engine/tests/functional/test_shipping.py` | FT-7.6 state; wait for that plan run; `drive_to_review` again; write `src/cart.py` with `return 2` | POST `S` | `reason` "shipped"; `len(host.mrs) == 1`; `shop.git` branch `limo/cart/TKT-1` has `return 2` |
| FT-7.8 | OP-1:idempotency, OP-4:idempotency | `engine/tests/functional/test_shipping.py` | shipped once | POST `S` again | `reason` is not "shipped"; `len(host.mrs) == 1`; `enable_auto_merge` appears once in `host.calls` |
| FT-7.9 | OP-1:external-failure, OP-4:external-failure | `engine/tests/functional/test_shipping.py` | `drive_to_review`; `host.fail_next.add("open_merge_request")` | POST `S`; then POST `S` again | 1st: 502 `host_error`, `host.mrs` empty, TKT-1 "review"; 2nd: `reason` "shipped", one MR |
| FT-7.10 | OP-2:validation | `engine/tests/functional/test_shipping.py` | cart project | POST `/api/projects/shop/features/Bad!/poll` | 422 `validation_error` |
| FT-7.11 | OP-2:not-found | `engine/tests/functional/test_shipping.py` | — | POST `/api/projects/nope/features/cart/poll` | 404 `project_not_found` |
| FT-7.12 | OP-2:idempotency | `engine/tests/functional/test_shipping.py` | FT-7.3 state | POST `P` again | `merged` == `[]`; TKT-1 still "done" |
| FT-7.13 | OP-2:boundary | `engine/tests/functional/test_shipping.py` | cart project, nothing shipped | POST `P` | `{"merged": [], "changes_requested": []}` |
| FT-7.14 | OP-2:external-failure | `engine/tests/functional/test_shipping.py` | shipped; `host.fail_next.add("merge_request_status")` | POST `P` | 502 `host_error`; TKT-1 still "review" |

## Context pack
- `engine/limo/runner/service.py`, `engine/limo/runner/models.py`, `engine/limo/runner/tickets.py` — STEP-8 edit / read
- `engine/limo/api/runner_routes.py` — STEP-9 edit
- `engine/limo/app.py` — STEP-10 edit
- `engine/limo/executor/ports.py` — read
- `engine/limo/projects/models.py`, `engine/limo/projects/repo.py` — read (`Project`, `default_branch`)
- `engine/limo/common/errors.py` — read
- `engine/limo/store/db.py` — read
- `engine/limo/inbox/repo.py` — like: repository pattern
- `engine/tests/conftest.py`, `engine/tests/builders.py` — STEP-2 edit
- `engine/tests/fakes/llm.py` — read (`stage_responder`)
- `engine/tests/functional/test_runner.py`:57-100 — STEP-12 edit
- `engine/limo/runner/shipping.py` — STEP-14 edit
- `engine/limo/vcs/git.py` — read (`start_ticket`)
- `engine/limo/hosts/repo.py` — STEP-16 edit

## Steps
### STEP-1 RepoHost port and default adapter
- file: `engine/limo/hosts/__init__.py` (empty), `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` (create)
- do: frozen dataclasses `HostProject(name: str, git_url: str, kind: str)`, `MergeRequestRef(number: int, url: str)`, `ReviewComment(id: str, body: str)`, `MrStatus(state: Literal["open", "merged", "closed"], approved: bool, change_requests: list[ReviewComment])`; `class HostError(Exception)`; `class RepoHost(Protocol)` with the three methods in Design › contracts. `UnconfiguredHost` implements them, each raising `HostError("repo host adapter not configured")`.
- verify: `cd engine && uv run python -c "import limo.hosts.ports, limo.hosts.unconfigured"` → exit 0

### STEP-2 fake host, fixtures, driver (test first)
- file: `engine/tests/fakes/host.py` (create), `engine/tests/conftest.py`, `engine/tests/builders.py` (edit)
- do:
  - `FakeHost` (implements `RepoHost`): `calls: list[tuple[str, int | str]]`, `mrs: dict[int, FakeMr]` (`FakeMr`: `branch, base, title, git_url, state="open", approved=False, comments: list[ReviewComment]`), `fail_next: set[str]`. Each port method first: `if name in fail_next: fail_next.discard(name); raise HostError("fake failure")`, then appends `(name, number-or-branch)` to `calls`. `open_merge_request` numbers MRs from 1, url `https://host.example/mr/<n>`. `merge_request_status` returns state, approved, comments (as change requests). Test controls (not in the port, not recorded in `calls`): `approve(n)`, `request_changes(n, body)` (comment id `c<count>`), `merge(n)`: clone the bare repo from `git_url` into a temp dir, `git checkout <base>`, `git -c user.name=t -c user.email=t@t merge --no-ff origin/<branch> -m merge`, `git push origin <base>`, set state `merged`.
  - conftest: fixture `host() -> FakeHost`; `client` builds `Deps(executor=…, llm=llm, host=host)`
  - builders: `drive_to_review(client, llm, settings, project="shop")` as described above the table (poll each started run until finished, like `start_and_wait`)
- verify: none until STEP-10

### STEP-3 tests
- file: `engine/tests/functional/test_shipping.py` (create)
- do: one function per FT-7.1 … FT-7.14; names `test_ft_7_<k>_<behavior>`, docstring starts `"""FT-7.<k> `; use `subprocess.run(["git", …], capture_output=True, text=True)` for remote checks; a local helper `_ship(client, llm, settings, host)` = `drive_to_review` + POST `S` asserting "shipped"
- verify: `mise run test:engine -- -k ft_7` → FAIL (fixture `host` unknown to `create_app` / 404 on poll)

### STEP-4 table
- file: `engine/limo/store/migrations/007_merge_requests.sql` (create)
```sql
CREATE TABLE merge_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  number INTEGER NOT NULL,
  url TEXT NOT NULL,
  branch TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('open', 'merged', 'closed')),
  last_review_id TEXT NOT NULL DEFAULT '',
  needs_push INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX merge_requests_feature ON merge_requests (project_id, feature, state);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-5 merge request repo
- file: `engine/limo/hosts/repo.py` (create)
- do: frozen dataclass `MrRecord(id: int, project_id, feature, ticket, number, url, branch, state, last_review_id, needs_push: bool)`; `MergeRequestRepo(db_path)`: `add(project_id, feature, ticket, ref: MergeRequestRef, branch)` — keep ≤ 5 params excl. self by passing a frozen `NewMr(project_id, feature, ticket, branch)` plus `ref`; `open_for(project_id, feature) -> list[MrRecord]`; `open_for_ticket(project_id, feature, ticket) -> MrRecord | None`; `set_state(id, state)`; `set_review(id, last_review_id, needs_push: bool)`; `set_needs_push(id, value: bool)`
- verify: `cd engine && uv run python -c "import limo.hosts.repo"` → exit 0

### STEP-6 git operations
- file: `engine/limo/vcs/__init__.py` (empty), `engine/limo/vcs/git.py` (create)
- do: `class GitError(Exception)`; `GitOps(executor: Executor, timeout_s: float)`; private `_git(workspace, *args) -> CommandResult` (runs `["git", *args]`; `ExecutorError` → `GitError`):
  - `start_ticket(workspace, branch, base)`: `fetch origin` (code ≠ 0 → `GitError`); if `rev-parse --verify --quiet refs/heads/<branch>` succeeds → `checkout <branch>`; elif `rev-parse --verify --quiet refs/remotes/origin/<branch>` succeeds → `checkout -B <branch> origin/<branch>`; else `checkout -B <branch> origin/<base>`; checkout failure → `GitError`
  - `commit_and_push(workspace, branch, message)`: `add -A -- . :(exclude)work`; `-c user.name=Limo -c user.email=limo@localhost commit -m <message>` (code 1 with "nothing to commit" in stdout → continue; other ≠ 0 → `GitError`); `push -u origin <branch>` (≠ 0 → `GitError`)
- verify: `cd engine && uv run python -c "import limo.vcs.git"` → exit 0

### STEP-7 shipping service
- file: `engine/limo/runner/shipping.py` (create), `engine/limo/runner/tickets.py` (edit)
- do:
  - `TicketBoard.set_status(workspace, project, feature, ticket, status)` — runs `["fx", "set", f"work/{feature}", ticket, f"status={status}"]` with the same env as `read`; failure → `Conflict("map_invalid", …)`. Keep ≤ 5 params excl. self: pass a frozen `TicketRef(workspace: Path, project: str, feature: str, ticket: str)` and `status`.
  - `PollResult(BaseModel)`: `merged: list[str]`, `changes_requested: list[str]` (in `runner/models.py`)
  - `ShippingService(git: GitOps, host: RepoHost, mrs: MergeRequestRepo, board: TicketBoard)`:
    - `needs_ship(project_id, feature, ticket) -> bool` = no open MR, or open MR with `needs_push`
    - `ship(project: Project, feature, ticket)`: `git.commit_and_push(workspace, branch, f"{ticket}: {feature}")`; open MR exists → `mrs.set_needs_push(id, False)`; else `ref = host.open_merge_request(HostProject(project.name, project.git_url, project.host), branch, project.default_branch, f"{ticket} ({feature})")`, `host.enable_auto_merge(…, ref.number)`, `mrs.add(…)`. `HostError` → `ExternalError("host_error", "repo host call failed")`; `GitError` → `ExternalError("git_failed", "git command failed")`
    - `poll(project, feature) -> PollResult`: for each open MR: status via host (`HostError` → `ExternalError("host_error", …)`); `merged` → `set_state(id, "merged")`, board status `done`, add to `merged`; else new comments = those after `last_review_id` (all when it is `""`); if any → write the review report (k = count of `work/<feature>/reports/<ticket>-review-*.md` + 1, lines `- <body>`), board status `todo`, `set_review(id, last new id, True)`, add to `changes_requested`
- verify: `cd engine && uv run python -c "import limo.runner.shipping"` → exit 0

### STEP-8 runner: ship first, branch before every run
- file: `engine/limo/runner/service.py`, `engine/limo/runner/models.py` (edit)
- do: `StepResult.reason` adds `"shipped"`. Group constructor deps into frozen `RunnerDeps(runs: RunService, projects: ProjectRepo, board: TicketBoard, inbox: InboxService, shipping: ShippingService, git: GitOps)`; constructor `(self, deps: RunnerDeps, max_concurrent: int)`. In `step`, after filtering held tickets: first state with status `review` where `shipping.needs_ship(project.id, feature, id)` → `shipping.ship(project, feature, id)` → return `StepResult(run=None, reason="shipped")`. Before `runs.start(...)`: `git.start_ticket(Path(project.workspace), f"limo/{feature}/{ticket}", project.default_branch)` (`GitError` → `ExternalError("git_failed", …)`). Add `poll(project_name, feature) -> PollResult` (project lookup → `shipping.poll`). Keep each method ≤ 40 lines (move the ship check into `_ship_pending`).
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-9 poll route
- file: `engine/limo/api/runner_routes.py` (edit)
- do: add `POST /api/projects/{name}/features/{feature}/poll` → `PollResult` (same feature pattern as step)
- verify: `cd engine && uv run python -c "import limo.api.runner_routes"` → exit 0

### STEP-10 wiring
- file: `engine/limo/app.py` (edit)
- do: `Deps` gains `host: RepoHost | None = None` (last field); use `deps.host or UnconfiguredHost()`; build `git = GitOps(deps.executor, settings.command_timeout_s)`, `board` once, `ShippingService(git, host, MergeRequestRepo(db), board)`, `RunnerService(RunnerDeps(runs, ProjectRepo(db), board, inbox, shipping, git), settings.max_concurrent_tickets)`
- verify: `mise run test:engine` → all pass (73 + 14 FT-7)

### STEP-11 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 87 passed

### STEP-12 update TKT-5 runner tests for shipping (revision 1: verify r0)
- file: `engine/tests/functional/test_runner.py` (edit)
- do:
  - FT-5.3: replace the last line `assert r.json()["reason"] == "no_ready_ticket"` with these lines (TKT-1 in review now ships once, then nothing starts):
```python
    assert r.json()["reason"] == "shipped"
    again = post_step(client)
    assert again.json()["run"] is None
    assert again.json()["reason"] == "no_ready_ticket"
```
  - FT-5.4: inside the loop, right after the `if first["reason"] == "no_ready_ticket": break` block, add:
```python
        if first["reason"] == "shipped":
            continue
```
  - change nothing else; the 12-iteration limit becomes 16 (`for _ in range(16):`) because each ticket now adds one ship step
- verify: `mise run test:engine` → 87 passed

### STEP-13 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 87 passed

### STEP-14 ship checks out the ticket branch first (revision 2: resolver escalation, human-approved)
- file: `engine/limo/runner/shipping.py` (edit)
- do: in `ship`, inside the existing `try` and before `commit_and_push`, add `self._git.start_ticket(Path(project.workspace), branch, project.default_branch)`; change nothing else
- verify: `mise run test:engine` → 87 passed

### STEP-15 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 87 passed

### STEP-16 type the row mapper (revision 3)
- file: `engine/limo/hosts/repo.py` (edit)
- do: change `def _record(row)` to `def _record(row: sqlite3.Row) -> MrRecord` (add `import sqlite3` if missing)
- verify: `mise run types` → `Success`

### STEP-17 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates`, `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 87 passed

## Do not
- add GitHub/GitLab HTTP adapters or tokens (TKT-18), issue mirroring (TKT-8), or a background poll loop (TKT-16)
- give the RepoHost port a merge method
- commit anything under `work/`
- add `# noqa`

## Doc updates
- context/INDEX.md: Shape — `engine/limo/hosts` (RepoHost port, unconfigured default, merge requests) and `engine/limo/vcs` (git via executor); `runner` line: ship + poll
- context/layout.md: module list adds `hosts`, `vcs`; fake ref `engine/tests/fakes/host.py`
- context/api.md: poll endpoint; step reason `shipped`
- context/data.md: `merge_requests` per `007_merge_requests.sql`
- context/testing.md: Fakes — GitLab / GitHub row → `FakeHost` in `engine/tests/fakes/host.py` (approve, request_changes, merge, fail_next); builder `drive_to_review`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
