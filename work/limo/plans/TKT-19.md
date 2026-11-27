---
ticket: TKT-19
feature: limo
scenarios: [SC-34, SC-35, SC-36, SC-62]
scope: [runner, agents, host]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/resolver.feature, work/limo/reports/TKT-9-close.md, skills/resolver/SKILL.md, DESIGN.md#Orchestration, context/INDEX.md, context/code-rules.md, context/security.md, context/testing.md, context/data.md, scripts/fx.py, engine/limo/incidents/*.py, engine/limo/hosts/*.py, engine/limo/agents/*.py, engine/limo/runner/service.py, engine/tests/fakes/*.py]
---
# TKT-19: Resolver answers questions, retitles, re-plans or escalates invalid actions

## Design
- where: `scripts/fx.py` gains `retitle`; RepoHost port gains `set_issue_title`, `add_issue_label`; `limo/incidents/` applies `answer`, `edit-ticket`, `replan`, `escalate` and writes the resolve report; runs gain `note` (appended to the task); migration `011_incident_notes.sql`
- responsibilities:
  - `fx retitle <work/feature> TKT-n <title words…>` — rewrites that ticket's `title:` line in map.yaml (title 1–120 chars, one line)
  - `limo.incidents.apply.ActionApplier` — one method per action type; returns the incident's new status
  - `IncidentService._apply` — writes `work/<f>/reports/<ticket>-resolve-<k>.md` (the resolver run's `output`, or `resolver run failed: <error>`), then applies via `ActionApplier`
  - escalation (explicit `escalate`, invalid/unparsable action, failed resolver run, second `replan`, a valid action that cannot be applied) → issue label `factory:needs-human`, incident `needs_human`
  - `RunnerService` — a plan run started for a ticket with an unconsumed replan note gets `note` = the fix; the note is then marked consumed
- reuse: `TicketBoard` env (for `fx retitle`/`set_status`), `IssueRepo.for_feature` (issue numbers), `HostProject`, `parse_action`, `RETRY_STATUS`
- contracts:
  - `answer {question: "Q-<n>", answer: str 1..500, source: str}` → in `work/<f>/questions.md` the heading `## Q-<n> [open]` becomes `## Q-<n> [answered]` and that section's `- answer:` line becomes `- answer: <answer> (source: <source>)`; ticket status `todo`; incident `resolved`. Question missing or not open → escalate
  - `edit-ticket {title: str 1..120, source: str}` → `fx retitle`; `host.set_issue_title(hp, number, f"{ticket}: {title}")` when the ticket has an issue; ticket `todo`; `resolved`. Bad title → escalate
  - `replan {fix: str 1..500, source: str}` → if any earlier incident of the ticket has action type `replan` → escalate; else write `work/<f>/reports/<ticket>-replan-<k>.md` = fix, set `note_pending = 1` on the incident, ticket `todo`, `resolved`
  - `escalate {summary, ask}` → escalate (comment and inbox come in TKT-10)
  - `retry` unchanged (TKT-9)
  - host failure while applying → 502 `host_error`; incident stays `open` (applied again on the next step)
  - plan task text with a note: `feature=<f> ticket=<t>\nnote: <fix>`
  - port additions: `set_issue_title(project, number, title) -> None`, `add_issue_label(project, number, label) -> None` (raise `HostError`)
- data: `incidents.note_pending INTEGER NOT NULL DEFAULT 0`; `runs.note TEXT`
- decisions: follows DESIGN.md › Resolver actions incl. `replan` (human-approved 2026-11-26), Q-5 labels, ADR-4 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): only allowlisted action types are applied; everything else escalates
- input validation: field types and lengths checked in `ActionApplier`; question id `^Q-\d+$`; titles single-line
- injection: `fx retitle` via argv list; questions.md edited by exact line match, never by evaluating text
- data exposure / PII: notes and answers stay in the local workspace (`work/` is never committed)
- secrets: none
- rate limit / abuse: one replan per ticket
- audit: resolve and replan reports in `work/<f>/reports/`; incident `action`
### Performance
- queries (N+1, indexes): one query for earlier replan actions per ticket
- pagination / limits: n/a
- payload size: fix/answer ≤ 500 chars
- caching: n/a
- external calls (timeouts/retries): host calls via port
- sync vs async: inside the step
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 apply `answer` | FT-19.1 | FT-19.5 | FT-19.5 | n/a: one answer per question | FT-19.10 | n/a: incident leaves `open` once applied | n/a: single field set | n/a: local file |
| OP-2 apply `edit-ticket` | FT-19.2 | FT-19.6 | n/a: ticket exists in the map | n/a: one title | n/a: any status | n/a: incident leaves `open` once applied | FT-19.6 | FT-19.7 |
| OP-3 escalate (explicit or invalid) | FT-19.9 | FT-19.3 | n/a: issue exists after sync | n/a: label add is idempotent on hosts | n/a: any incident | n/a: incident leaves `open` once | n/a: one label | FT-19.11 |
| OP-4 apply `replan` + note on next plan run | FT-19.4 | n/a: fix text validated like answer (FT-19.5 pattern) | n/a: ticket exists | n/a: one note per ticket | FT-19.4 | FT-19.12 | n/a: single note | n/a: local |
| OP-5 resolve report | FT-19.8 | n/a: output text | n/a: run exists | n/a: one file per incident | n/a: written for every applied incident | n/a: written once | n/a: output already bounded | FT-19.8 |
| OP-6 `fx retitle` | FT-19.2 | FT-19.6 | n/a: unknown id → fx error → escalate | n/a: one title line | n/a: any status | n/a: same title rewrites the same line | n/a: one line | n/a: local |

## Functional tests
File `engine/tests/functional/test_resolver_actions.py`. Setup per test: `add_cart_project(client, tmp_path)` (`tests/builders.py`); first `POST /api/projects/shop/features/cart/step` with nothing stuck is not needed — issues are created by the step that opens the incident. Make TKT-1 stuck with `set_status(settings, "shop", "TKT-1", "blocked")` unless stated. Resolver answers come from `llm.responder = resolver_responder(settings.skills_dir, "```json\n<json>\n```")` (`tests/fakes/llm.py`). Flow: POST step → `reason` "resolving"; `wait_run(client, r.json()["run"]["id"])`; POST step → read `reason`. Incidents: `GET /api/projects/shop/features/cart/incidents`. Issue labels/titles: `host.issues[n].labels` / `.title` where `n` is the TKT-1 issue (title starts `TKT-1:`). Workspace files under `settings.workspaces_dir / "shop"`. Ticket titles: run `fx tickets work/cart` via `subprocess` with `fx_env(settings, "shop")`, cwd = workspace.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-19.1 | SC-34, OP-1:happy | `engine/tests/functional/test_resolver_actions.py` | `write_workspace_file … "work/cart/questions.md", "## Q-3 [open] Which currency?\n- blocks: TKT-1\n- answer:\n"` (TKT-1 stays todo); action `{"type": "answer", "question": "Q-3", "answer": "use EUR", "source": "context/data.md:12"}` | flow | 2nd step `reason` "resolved"; questions.md contains `## Q-3 [answered]` and `- answer: use EUR (source: context/data.md:12)`; TKT-1 status "todo" |
| FT-19.2 | SC-35, OP-2:happy, OP-6:happy | `engine/tests/functional/test_resolver_actions.py` | blocked; action `{"type": "edit-ticket", "title": "Cart total includes tax", "source": "x"}` | flow, then POST step | 2nd step "resolved"; `fx tickets` first line `TKT-1\tCart total includes tax`; TKT-1 issue title `TKT-1: Cart total includes tax`; 3rd step `run.agent` "plan", `run.ticket` "TKT-1" |
| FT-19.3 | SC-36, OP-3:validation | `engine/tests/functional/test_resolver_actions.py` | blocked; action `{"type": "merge"}` | flow | `reason` "needs_human"; TKT-1 issue labels contain `factory:needs-human` |
| FT-19.4 | SC-62, OP-4:happy, OP-4:invalid-state | `engine/tests/functional/test_resolver_actions.py` | blocked; action `{"type": "replan", "fix": "define IssueRef before the fake host step", "source": "x"}` | flow; POST step (plan starts) + wait; `set_status TKT-1 blocked`; flow again | 1st flow "resolved", TKT-1 "todo"; the plan run's first LLM request `messages[0]["content"]` contains `note: define IssueRef before the fake host step`; `work/cart/reports/TKT-1-replan-1.md` exists; 2nd flow `reason` "needs_human" and label `factory:needs-human` |
| FT-19.5 | OP-1:validation, OP-1:not-found | `engine/tests/functional/test_resolver_actions.py` | blocked; parametrize action `{"type": "answer", "question": "Q-9", "answer": "x", "source": "y"}` (no such question) and `{"type": "answer", "question": "Q-3", "answer": "", "source": "y"}` | flow | `reason` "needs_human" |
| FT-19.6 | OP-2:validation, OP-2:boundary, OP-6:validation | `engine/tests/functional/test_resolver_actions.py` | blocked; parametrize title `""`, `"a" * 121`, `"two\nlines"` | flow | `reason` "needs_human"; `fx tickets` first line unchanged (`TKT-1\tCart shows a total`) |
| FT-19.7 | OP-2:external-failure | `engine/tests/functional/test_resolver_actions.py` | blocked; edit-ticket action; after the resolver run finished `host.fail_next.add("set_issue_title")` | POST step; POST step | 1st: 502 `host_error`, incident still `open`; 2nd: `reason` "resolved" |
| FT-19.8 | OP-5:happy, OP-5:external-failure | `engine/tests/functional/test_resolver_actions.py` | blocked; parametrize: retry action (resolver succeeds) / `llm.fail_with = LlmError("down")` set before the first step (resolver run fails) | flow | `work/cart/reports/TKT-1-resolve-1.md` exists; success case contains `"retry"`; failure case contains `resolver run failed` |
| FT-19.9 | OP-3:happy | `engine/tests/functional/test_resolver_actions.py` | blocked; action `{"type": "escalate", "summary": "s", "ask": "Should totals include tax?"}` | flow | `reason` "needs_human"; label `factory:needs-human` |
| FT-19.10 | OP-1:invalid-state | `engine/tests/functional/test_resolver_actions.py` | questions.md with `## Q-3 [answered] Which currency?\n- blocks: TKT-1\n- answer: EUR\n`; TKT-1 blocked; action answer Q-3 | flow | `reason` "needs_human" (question not open) |
| FT-19.11 | OP-3:external-failure | `engine/tests/functional/test_resolver_actions.py` | blocked; action `{"type": "merge"}`; after the resolver run finished `host.fail_next.add("add_issue_label")` | POST step; POST step | 1st: 502 `host_error`; 2nd: `reason` "needs_human", label present |
| FT-19.12 | OP-4:idempotency | `engine/tests/functional/test_resolver_actions.py` | FT-19.4 up to the plan run | POST step again after that plan run (fake answers `final()`) and wait if a run starts | no later plan run for TKT-1 has `note:` in its task (note consumed once) |

## Context pack
- `scripts/fx.py`:1-20, 196-215, 360-395 — STEP-1 edit
- `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` — STEP-2 edit
- `engine/tests/fakes/host.py` — STEP-3 edit
- `engine/limo/hosts/issue_repo.py` — read
- `engine/limo/incidents/service.py`, `engine/limo/incidents/repo.py`, `engine/limo/incidents/actions.py`, `engine/limo/incidents/models.py` — STEP-6..8 edit
- `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` — STEP-5 edit
- `engine/limo/runner/service.py`, `engine/limo/runner/tickets.py` — STEP-9 edit / read
- `engine/limo/app.py` — STEP-10 edit
- `engine/limo/common/errors.py`, `engine/limo/projects/models.py`, `engine/limo/store/db.py` — read
- `engine/tests/builders.py`, `engine/tests/conftest.py`, `engine/tests/fakes/llm.py`, `engine/tests/functional/test_incidents.py` — read (helpers; FT-9 flow pattern)

## Steps
### STEP-1 fx retitle
- file: `scripts/fx.py` (edit)
- do: `cmd_retitle(work, ticket, title)`: title must be 1–120 chars without newline else `die("bad title")`; read `map.yaml` lines; after the line `  - id: <ticket>` replace the first following `    title:` line with `    title: <title>`; unknown ticket → `die`; write back. Dispatch `elif c == "retitle" and len(rest) >= 3: cmd_retitle(rest[0], rest[1], " ".join(rest[2:]))`; usage line `fx.py retitle <work/feature> TKT-n <title>`
- verify: `cp -r work/limo /tmp/claude-1000/fxr && fx retitle /tmp/claude-1000/fxr TKT-1 New title && fx tickets /tmp/claude-1000/fxr | head -1; rm -rf /tmp/claude-1000/fxr` → `TKT-1	New title`

### STEP-2 port
- file: `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` (edit)
- do: add `set_issue_title(self, project: HostProject, number: int, title: str) -> None` and `add_issue_label(self, project: HostProject, number: int, label: str) -> None` to `RepoHost`; `UnconfiguredHost` raises `HostError` for both
- verify: `cd engine && uv run python -c "import limo.hosts.unconfigured"` → exit 0

### STEP-3 fake host
- file: `engine/tests/fakes/host.py` (edit)
- do: both methods check `fail_next`, record `(name, number)` in `calls`; `set_issue_title` sets `issues[n].title`; `add_issue_label` appends the label if missing
- verify: `mise run test:engine -- -k ft_8` → passed

### STEP-4 tests (test first)
- file: `engine/tests/functional/test_resolver_actions.py` (create)
- do: one function per FT-19.1 … FT-19.12 (FT-19.5, FT-19.6, FT-19.8 parametrized); names `test_ft_19_<k>_<behavior>`, docstring starts `"""FT-19.<k> `; a local helper `_flow(client) -> dict` = POST step (assert "resolving"), `wait_run`, POST step, return the json
- verify: `mise run test:engine -- -k ft_19` → FAIL (actions end in `needs_human`, no files)

### STEP-5 runs carry a note
- file: `engine/limo/store/migrations/011_incident_notes.sql` (create), `engine/limo/agents/models.py`, `engine/limo/agents/repo.py`, `engine/limo/agents/service.py` (edit)
```sql
ALTER TABLE incidents ADD COLUMN note_pending INTEGER NOT NULL DEFAULT 0;
ALTER TABLE runs ADD COLUMN note TEXT;
```
- do: `RunIn.note: str | None = Field(default=None, max_length=500)`; `Run.note: str | None = None`; stored and read; task text gets `f"\nnote: {note}"` appended when set
- verify: `mise run test:engine` → all earlier tests pass

### STEP-6 incident repo additions
- file: `engine/limo/incidents/repo.py`, `engine/limo/incidents/models.py` (edit)
- do: `IncidentRow` gains `k: int` access (exists) and `note_pending: bool`; repo: `actions_for(project_id, feature, ticket) -> list[str]` (non-null `action` texts); `set_note_pending(id, value: bool)`; `pending_note(project_id, feature, ticket) -> tuple[str, str] | None` (incident id, `fix` from its action JSON, newest with `note_pending = 1`)
- verify: `cd engine && uv run python -c "import limo.incidents.repo"` → exit 0

### STEP-7 action applier
- file: `engine/limo/incidents/apply.py` (create)
- do: frozen `ApplyContext(project: Project, feature: str, incident: IncidentRow)`; `ActionApplier(board: TicketBoard, host: RepoHost, issues: IssueRepo, repo: IncidentRepo)` with `apply(ctx, action: dict[str, Any] | None) -> Literal["resolved", "needs_human"]`: dispatch by type to `_retry`, `_answer`, `_edit_ticket`, `_replan`; anything else, `None`, or a handler returning `False` → `_escalate(ctx)` (label `factory:needs-human` on the ticket's issue when one exists) and `"needs_human"`. `HostError` → `ExternalError("host_error", "repo host call failed")`. Answer edits `questions.md` by lines: find the heading line starting `## <Q> [open]`; replace `[open]` by `[answered]`; within the section (until the next `## `) replace the line starting `- answer:`; if no such line, insert it after the heading's last section line. `fx retitle` runs through the board's executor with the board env (add `TicketBoard.retitle(ref: TicketRef, title: str) -> None` there; failure → `Conflict("map_invalid", …)`). Each method ≤ 40 lines.
- verify: `cd engine && uv run python -c "import limo.incidents.apply"` → exit 0

### STEP-8 service uses the applier and writes the report
- file: `engine/limo/incidents/service.py` (edit), `engine/limo/runner/tickets.py` (edit)
- do: group constructor deps into frozen `IncidentDeps(repo, runs, board, applier)` → `IncidentService(deps, timeout_s)`; `_apply` writes `work/<f>/reports/<ticket>-resolve-<k>.md` (output, or `resolver run failed: <error>`), computes `action = None if failed else parse_action(output)`, calls `applier.apply(...)`, stores the result status and `json.dumps(action, sort_keys=True)` (or None), returns `StepResult(run=None, reason=<status>)`. Add `consume_note(project_id, feature, ticket) -> str | None` (returns the fix and clears `note_pending`).
- verify: `cd engine && uv run python -c "import limo.incidents.service"` → exit 0

### STEP-9 runner passes the note
- file: `engine/limo/runner/service.py` (edit)
- do: when the dispatched agent is `plan`, `note = self._incidents.consume_note(project.id, feature, ticket)` and pass `note=note` in `RunIn`
- verify: `cd engine && uv run python -c "import limo.runner.service"` → exit 0

### STEP-10 wiring
- file: `engine/limo/app.py` (edit)
- do: `ActionApplier(board, host, IssueRepo(db), incident_repo)`; `IncidentService(IncidentDeps(incident_repo, runs, board, applier), settings.run_timeout_s)`
- verify: `mise run test:engine` → all passed

### STEP-11 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fixes), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

## Do not
- add issue comments, inbox holds, or the 2-resolve limit (TKT-10)
- let the resolver run itself write files (the runner writes its report)
- add `# noqa`

## Doc updates
- context/INDEX.md: `incidents` line — all actions applied (retry, answer, edit-ticket, replan, escalate → label)
- context/data.md: `incidents.note_pending`; `runs.note`
- context/testing.md: FakeHost `set_issue_title`, `add_issue_label`
- DESIGN.md: Factory repo layout — fx gains `retitle`
- skills/resolver/SKILL.md: Step 4 — "The runner writes the report from your final message; put the report text (template) in your final answer" (drift from TKT-9 close)
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
