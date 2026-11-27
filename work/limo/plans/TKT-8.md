---
ticket: TKT-8
feature: limo
scenarios: [SC-30, SC-31]
scope: [host]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/host.feature, work/limo/questions.md#Q-5, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/data.md, ADR-3:L2, ADR-4:L2, scripts/fx.py, engine/limo/hosts/*.py, engine/limo/runner/service.py, engine/limo/runner/tickets.py, engine/tests/fakes/host.py]
---
# TKT-8: Tickets are mirrored to repo host issues

## Design
- where: `scripts/fx.py` gains `tickets`; RepoHost port gains issue methods; new `limo/hosts/issues.py` (IssueService) + `issues` table; `RunnerService.step` syncs issues once a feature is in the `tickets` phase; `FakeHost` gains issues
- responsibilities:
  - `fx tickets <work/feature>` — prints `<id>\t<title>` per ticket in map order (titles stay single-sourced in map.yaml)
  - `TicketBoard.titles(workspace, project, feature) -> dict[str, str]` — runs `fx tickets`
  - `limo.hosts.issues.IssueService.sync(project, feature, states)` — create a missing issue per ticket (title `"<id>: <title>"`), then make each issue's status label match the ticket status when it changed since the last sync
  - `RunnerService.step` — after the phase check says `tickets` and the board is read (before shipping/dispatch), call `issues.sync`
- reuse: `TicketBoard` env/parse, `HostProject`, `HostError` → `ExternalError("host_error")`, repo pattern
- contracts:
  - port additions (raise `HostError` on failure): `create_issue(project: HostProject, title: str) -> IssueRef` (`IssueRef(number: int, url: str)`); `set_issue_status(project: HostProject, number: int, status: str) -> None` — adapters put label `limo:<status>` on the issue and remove any other `limo:*` label (Q-5)
  - issues are created for every ticket in map order on the first sync of the feature (Q-5: at spec time = the step right after spec passes map-check); new tickets added later get an issue on the next sync
  - a sync makes no host call for a ticket whose status equals its last mirrored status
  - host failure during sync → 502 `host_error`; rows are written only after the host call succeeds, so the next step retries
- data: `issues(project_id, feature, ticket, number, url, status, PRIMARY KEY(project_id, feature, ticket))`
- decisions: follows ADR-3 (titles via fx), ADR-4 (port), Q-5 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a
- input validation: titles come from map.yaml through fx; status from the fixed status set
- injection: fx via argv; SQL parameterized
- data exposure / PII: issue titles are ticket titles only (no requirements text)
- secrets: none
- rate limit / abuse: host calls only on change
- audit: `issues` rows
### Performance
- queries (N+1, indexes): one query loads all issue rows of a feature; PK index
- pagination / limits: n/a
- payload size: n/a
- caching: last mirrored status stored, so unchanged tickets cost nothing
- external calls (timeouts/retries): via port; adapters set timeouts (TKT-18)
- sync vs async: inside the step request
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 create missing issues (sync) | FT-8.1 | n/a: titles validated by fx map parsing | n/a: feature/project checked by step (TKT-5) | FT-8.3 | n/a: any phase-`tickets` feature | FT-8.3 | FT-8.4 | FT-8.5 |
| OP-2 mirror status label (sync) | FT-8.2 | n/a: statuses from a fixed set | n/a: issue row exists after OP-1 | n/a: one label per status | n/a: every status mirrors | FT-8.6 | n/a: one label | FT-8.7 |
| OP-3 `fx tickets` | FT-8.1 | n/a: map validated by `load_map` | n/a: covered by TKT-5 FT-5.7 | n/a: read only | n/a: read only | n/a: read only | FT-8.4 | n/a: local |

## Functional tests
All in `engine/tests/functional/test_issues.py`. `host.issues` (STEP-2) maps number → `FakeIssue(title, labels: list[str])`. Step = `POST /api/projects/shop/features/<feature>/step`; runs end with `wait_run`. Errors `r.json()["error"]["code"]`.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-8.1 | SC-30, OP-1:happy, OP-3:happy | `engine/tests/functional/test_issues.py` | shop with `context/` (`write_workspace_file … "context/INDEX.md"`); intake `posts`; step → spec run; wait; write `work/posts/map.yaml` with `TKT-1` titled `Posts can be listed` (scenario SC-1) + `work/posts/features/a.feature` (`@SC-1 @REQ-1`) + `work/posts/nfr.md` header only | POST step for `posts` | `[i.title for i in host.issues.values()] == ["TKT-1: Posts can be listed"]`; its labels == `["limo:todo"]` |
| FT-8.2 | SC-31, OP-2:happy | `engine/tests/functional/test_issues.py` | shop (feature `cart`, no intake row); step; wait; `set_status(… "TKT-1", "planned")`; step; wait | `set_status(… "TKT-1", "built")`; POST step | issue `TKT-1: Cart shows a total` has label `limo:built` and no `limo:planned` |
| FT-8.3 | OP-1:conflict, OP-1:idempotency | `engine/tests/functional/test_issues.py` | shop; step; wait | POST step again | `len(host.issues) == 3` (TKT-1..3); `create_issue` appears 3 times in `host.calls` |
| FT-8.4 | OP-1:boundary, OP-3:boundary | `engine/tests/functional/test_issues.py` | shop | POST step | issue titles in number order == `["TKT-1: Cart shows a total", "TKT-2: Cart total includes tax", "TKT-3: Cart can be emptied"]` |
| FT-8.5 | OP-1:external-failure | `engine/tests/functional/test_issues.py` | shop; `host.fail_next.add("create_issue")` | POST step; then POST step | 1st: 502 `host_error`, no issues; 2nd: 3 issues |
| FT-8.6 | OP-2:idempotency | `engine/tests/functional/test_issues.py` | shop; step; wait (TKT-1 stays `todo`: the fake plan run does not change it) | POST step | no new `set_issue_status` call for TKT-1 after the first sync (count of `("set_issue_status", <TKT-1 number>)` in `host.calls` is 1) |
| FT-8.7 | OP-2:external-failure | `engine/tests/functional/test_issues.py` | shop; step; wait; `set_status(… "TKT-1", "planned")`; `host.fail_next.add("set_issue_status")` | POST step; then POST step | 1st: 502 `host_error`; 2nd: TKT-1 issue has `limo:planned` |

## Context pack
- `scripts/fx.py`:1-15, 190-205, 355-380 — STEP-1 edit (`cmd_tickets`, dispatch, usage line at the top)
- `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` — STEP-3 edit
- `engine/limo/hosts/repo.py` — like: repository pattern
- `engine/limo/runner/tickets.py` — STEP-5 edit
- `engine/limo/runner/service.py` — STEP-6 edit
- `engine/limo/app.py` — STEP-7 edit
- `engine/limo/common/errors.py`, `engine/limo/store/db.py`, `engine/limo/projects/models.py` — read
- `engine/tests/fakes/host.py` — STEP-2 edit
- `engine/tests/builders.py`, `engine/tests/conftest.py` — read

## Steps
### STEP-1 fx tickets
- file: `scripts/fx.py` (edit)
- do: add `cmd_tickets(work)`: `_, tickets = load_map(work)`; print `f"{t['id']}\t{t['title']}"` per ticket; dispatch `elif c == "tickets": cmd_tickets(rest[0])`; add a usage line `fx.py tickets <work/feature>  print id<TAB>title per ticket`
- verify: `fx tickets work/limo | head -1` → `TKT-1	A user adds a project and sees the seven agents`

### STEP-2 fake host issues (test first)
- file: `engine/tests/fakes/host.py` (edit), `engine/tests/functional/test_issues.py` (create)
- do: `FakeIssue(title: str, labels: list[str])`; `FakeHost.issues: dict[int, FakeIssue]`; `create_issue` (checks `fail_next`, records `("create_issue", title)`, numbers from 1) and `set_issue_status` (checks `fail_next`, records `("set_issue_status", number)`, removes labels starting `limo:`, appends `limo:<status>`). Then write FT-8.1 … FT-8.7; names `test_ft_8_<k>_<behavior>`, docstring starts `"""FT-8.<k> `.
- verify: `mise run test:engine -- -k ft_8` → FAIL (no issues created)

### STEP-3 port
- file: `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` (edit)
- do: add `IssueRef(number: int, url: str)` and the two methods to `RepoHost`; `UnconfiguredHost` raises `HostError` for both
- verify: `cd engine && uv run python -c "import limo.hosts.unconfigured"` → exit 0

### STEP-4 table and repo
- file: `engine/limo/store/migrations/009_issues.sql` (create), `engine/limo/hosts/issue_repo.py` (create)
```sql
CREATE TABLE issues (
  project_id TEXT NOT NULL REFERENCES projects(id),
  feature TEXT NOT NULL,
  ticket TEXT NOT NULL,
  number INTEGER NOT NULL,
  url TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (project_id, feature, ticket)
);
```
- do: `IssueRepo(db_path)`: `for_feature(project_id, feature) -> dict[str, IssueRow]` (`IssueRow(ticket, number, url, status)` frozen dataclass); `add(project_id, feature, row: IssueRow)`; `set_status(project_id, feature, ticket, status)`
- verify: `cd engine && uv run python -c "import limo.hosts.issue_repo"` → exit 0

### STEP-5 titles on the board
- file: `engine/limo/runner/tickets.py` (edit)
- do: `TicketBoard.titles(workspace, project, feature) -> dict[str, str]` runs `["fx", "tickets", f"work/{feature}"]` (same env); parse `id\ttitle` lines; failure → `Conflict("map_invalid", …)`
- verify: `cd engine && uv run python -c "import limo.runner.tickets"` → exit 0

### STEP-6 issue service and runner hook
- file: `engine/limo/hosts/issues.py` (create), `engine/limo/runner/service.py` (edit)
- do:
  - `IssueService(host: RepoHost, repo: IssueRepo, board: TicketBoard)`: `sync(project: Project, feature: str, states: list[TicketState]) -> None`: rows = `repo.for_feature`; titles loaded only when some ticket has no row; for each state in order: no row → `ref = host.create_issue(hp, f"{id}: {title}")`, `host.set_issue_status(hp, ref.number, status)`, `repo.add(...)` (status = current); row with different status → `host.set_issue_status(...)`, `repo.set_status(...)`. `HostError` → `ExternalError("host_error", "repo host call failed")`.
  - `RunnerDeps` gains `issues: IssueService`; in `step`, right after `states, ready = self._board.read(...)` (before held-ticket filtering): `self._issues.sync(project, feature, states)`
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-7 wiring
- file: `engine/limo/app.py` (edit)
- do: `IssueService(host, IssueRepo(db), board)` into `RunnerDeps`
- verify: `mise run test:engine` → 107 passed (100 + 7)

### STEP-8 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fixes), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` → 107 passed

## Do not
- put requirements text or plans into issues
- add escalation labels or comments (TKT-10)
- change shipping or polling
- add `# noqa`

## Doc updates
- context/INDEX.md: `hosts` line — also issues: one per ticket, label `limo:<status>`
- context/data.md: `issues` per `009_issues.sql`
- context/testing.md: FakeHost issues (`issues`, `create_issue`, `set_issue_status`)
- DESIGN.md: Factory repo layout — fx gains `tickets`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
