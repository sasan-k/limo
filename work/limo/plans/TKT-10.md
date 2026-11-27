---
ticket: TKT-10
feature: limo
scenarios: [SC-37, SC-38, SC-39, SC-53]
scope: [runner, host]
revision: 5  # rev 4 + continue_item check order (unknown id → 404 before response check); human chose the revision path
run: from-STEP-11
read: [work/limo/map.yaml, work/limo/features/resolver.feature, work/limo/questions.md#Q-6, DESIGN.md#Orchestration, context/INDEX.md, context/code-rules.md, context/security.md, context/testing.md, context/data.md, context/api.md, engine/limo/incidents/*.py, engine/limo/inbox/*.py, engine/limo/api/inbox_routes.py, engine/limo/hosts/ports.py, engine/limo/runner/service.py, engine/tests/fakes/host.py]
---
# TKT-10: Escalations reach a human and replies come back

## Design
- where: RepoHost port gains `comment_issue`, `issue_comments`; incidents gain `ask`, `reply`, `human_input`, `last_comment_id`; escalation comments on the issue; resolve limit; poll picks up human replies; inbox lists escalations and Continue takes a response; migration `012_escalations.sql`
- responsibilities:
  - `ActionApplier._escalate` — label `factory:needs-human` (TKT-19) **and** one comment: `Limo needs a human.\n\n<summary>\n\nQuestion: <ask>` (summary/ask from an `escalate` action, else summary `Resolver could not act (<reason>)` and ask `What should Limo do with <ticket>?`); stores `ask` on the incident
  - `IncidentService._open_next` — when the ticket already has 2 incidents that the resolver handled with `human_input = 0`, the new incident is created directly as `needs_human` (no resolver run) and escalated; step → `needs_human`
  - `IncidentService.collect_replies(project, feature)` (called from `RunnerService.poll`) — for each `needs_human` incident with no `reply` whose ticket has an issue: the first host comment with `mine = False` newer than `last_comment_id` becomes the incident's `reply`
  - `IncidentService._follow_up` (in `handle`, before `_open_next`) — a `needs_human` incident with a `reply` → mark it `resolved`, open a new incident (trigger `human-reply`, `human_input = 1`) whose bundle adds `- human reply: <reply>`, start the resolver run → `resolving`
  - `RunnerService.inbox()` — budget holds + escalations (`needs_human` incidents without a reply) as one list; `RunnerService.continue_item(id, response)` — a hold id → budget continue (TKT-17); an incident id → requires `response`, posts it as an issue comment (mine), stores it as the incident's `reply`, then takes one step
- reuse: `ActionApplier`, `IssueRepo`, `HoldRepo`/`InboxService`, `RunnerService.step`, `parse_action`
- contracts:
  - port: `comment_issue(project, number, body) -> None`; `issue_comments(project, number) -> list[IssueComment]`, `IssueComment(id: str, body: str, mine: bool)` (ordered oldest first); both raise `HostError`
  - `GET /api/inbox` → `[InboxItem]`; `InboxItem` = `{"id", "project", "feature", "ticket", "kind": "budget"|"escalation", "reason", "created_at", "link": str | null}` (escalation: `reason` = ask, `link` = issue url)
  - `POST /api/inbox/{id}/continue` body optional `{"response": str 1..2000}` → 200 `StepResult` · 404 `hold_not_found` · 409 `hold_cleared` (budget hold already continued, or escalation already answered) · 422 `response_required` (escalation without a response)
  - `GET …/incidents` items gain `"id"` and `"human_input": bool`
  - resolve limit counts incidents with `resolver_run_id` set and `human_input = 0`; human-reply incidents never count (Q-6)
  - step `reason` values unchanged
- data: `incidents.ask TEXT`, `incidents.reply TEXT`, `incidents.human_input INTEGER NOT NULL DEFAULT 0`, `incidents.last_comment_id TEXT`
- decisions: follows Q-6 (reply auto-triggers the resolver, not counted; Continue in the inbox), DESIGN.md › Resolver (max 2 resolves), ADR-4 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): only comments with `mine = False` count as human replies
- input validation: response 1–2000 chars; continue id looked up in holds, then incidents
- injection: comment text is plain text to the host API; SQL parameterized
- data exposure / PII: replies stay in the local workspace bundle and incident row
- secrets: none
- rate limit / abuse: escalation posts one comment per incident
- audit: incident `ask`, `reply`, `human_input`
### Performance
- queries (N+1, indexes): replies checked only for `needs_human` incidents of the polled feature
- pagination / limits: n/a
- payload size: response ≤ 2000 chars
- caching: `last_comment_id` avoids re-reading old comments
- external calls (timeouts/retries): via port
- sync vs async: inside poll/step/continue requests
- NFR targets: none

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 escalate with comment | FT-10.2 | n/a: action validated in TKT-19 | n/a: issue created by sync | n/a: one comment per incident | n/a: any escalation | n/a: incident leaves `open` once | n/a: one comment | FT-10.5 |
| OP-2 resolve limit | FT-10.1 | n/a: count only | n/a: ticket exists | n/a: one incident at a time | FT-10.1 | n/a: limit re-checked per incident | FT-10.6 | n/a: local |
| OP-3 collect replies (poll) + follow-up (step) | FT-10.3 | FT-10.8 | n/a: issue exists | n/a: one reply per incident | n/a: only `needs_human` incidents | FT-10.7 | n/a: first reply wins | FT-10.13 |
| OP-4 continue an escalation | FT-10.4 | FT-10.9 | FT-10.10 | FT-10.11 | n/a: only listed items | FT-10.11 | n/a: single item | FT-10.12 |
| OP-5 inbox list | FT-10.4 | n/a: no parameters | n/a: list | n/a: read only | n/a: read only | n/a: read only | FT-10.14 | n/a: no external call |

## Functional tests
File `engine/tests/functional/test_escalations.py`. Helpers from `tests/builders.py`: `add_cart_project`, `set_status`, `wait_run`, `write_workspace_file`; fakes: `resolver_responder(settings.skills_dir, text)` (`tests/fakes/llm.py`), `host` fixture (`tests/fakes/host.py`, STEP-3 adds `reply(number, body)` and `issues[n].comments`). Endpoints: step `POST /api/projects/shop/features/cart/step`; poll `POST /api/projects/shop/features/cart/poll`; incidents `GET /api/projects/shop/features/cart/incidents`; inbox `GET /api/inbox`; continue `POST /api/inbox/{id}/continue` with JSON `{"response": "…"}`. Read `r.json()["reason"]`, `r.json()["run"]["agent"]`, errors `r.json()["error"]["code"]`. A "flow" = POST step (expect "resolving") → `wait_run` on its run → POST step. TKT-1 issue = the `host.issues` entry whose title starts `TKT-1:`. Escalate action text: `` "```json\n" + json.dumps({"type": "escalate", "summary": "Tax rule unclear", "ask": "Should totals include tax?"}) + "\n```" ``; retry text likewise with `{"type": "retry", "stage": "build"}`.

| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-10.1 | SC-37, OP-2:happy, OP-2:invalid-state | `engine/tests/functional/test_escalations.py` | retry responder; twice: `set_status TKT-1 blocked` + flow (each ends "resolved") | `set_status TKT-1 blocked`; POST step | `reason` "needs_human"; no run started (`run` null); 3rd incident `status` "needs_human", `trigger` "blocked"; TKT-1 issue has label `factory:needs-human` and one comment from Limo |
| FT-10.2 | SC-38, OP-1:happy | `engine/tests/functional/test_escalations.py` | TKT-1 blocked; escalate responder | flow; then POST step | flow ends "needs_human"; TKT-1 issue comments contain `Should totals include tax?`; label present; the next step starts a run with `run.ticket` == "TKT-3" (TKT-2 waits on TKT-1) |
| FT-10.3 | SC-39, OP-3:happy | `engine/tests/functional/test_escalations.py` | FT-10.2 state before its last step; `host.reply(<TKT-1 issue number>, "Yes, 21% VAT")` | POST poll; POST step | step `reason` "resolving", `run.agent` "resolver"; `work/cart/incidents/TKT-1-2.md` contains `Yes, 21% VAT`; incidents: #1 `resolved`, #2 `human_input` true |
| FT-10.4 | SC-53, OP-4:happy, OP-5:happy | `engine/tests/functional/test_escalations.py` | FT-10.1 state (limit reached, escalated) | GET inbox; POST continue `{"response": "Yes, 21% VAT"}` with the escalation item's `id` | inbox has an item `kind` "escalation", `ticket` "TKT-1", `link` == the issue url; continue → `reason` "resolving", `run.agent` "resolver"; TKT-1 issue comments contain a Limo comment `Yes, 21% VAT`; newest bundle `work/cart/incidents/TKT-1-4.md` contains it; GET inbox has no escalation item |
| FT-10.5 | OP-1:external-failure | `engine/tests/functional/test_escalations.py` | TKT-1 blocked; escalate responder; POST step + wait; `host.fail_next.add("comment_issue")` | POST step; POST step | 1st 502 `host_error` and incident #1 still `open`; 2nd "needs_human" |
| FT-10.6 | OP-2:boundary | `engine/tests/functional/test_escalations.py` | one retry cycle (blocked + flow → resolved) | `set_status TKT-1 blocked`; POST step | `reason` "resolving" (1 prior resolve is under the limit) |
| FT-10.7 | OP-3:idempotency | `engine/tests/functional/test_escalations.py` | FT-10.3 state after the poll | POST poll again; POST step | exactly one incident with `human_input` true |
| FT-10.8 | OP-3:validation | `engine/tests/functional/test_escalations.py` | FT-10.2 state (escalated; Limo's own comment is on the issue) | POST poll; POST step | no new incident; step does not return "resolving" for TKT-1 |
| FT-10.9 | OP-4:validation | `engine/tests/functional/test_escalations.py` | FT-10.1 state | POST continue on the escalation with `{}`; with `{"response": ""}` | 422 `response_required`; 422 `validation_error` |
| FT-10.10 | OP-4:not-found | `engine/tests/functional/test_escalations.py` | — | POST `/api/inbox/nope/continue` `{"response": "x"}` | 404 `hold_not_found` |
| FT-10.11 | OP-4:conflict, OP-4:idempotency | `engine/tests/functional/test_escalations.py` | FT-10.4 after the first continue | POST the same continue again | 409 `hold_cleared` |
| FT-10.12 | OP-4:external-failure | `engine/tests/functional/test_escalations.py` | FT-10.1 state; `host.fail_next.add("comment_issue")` | POST continue `{"response": "x"}` | 502 `host_error`; inbox still lists the escalation |
| FT-10.13 | OP-3:external-failure | `engine/tests/functional/test_escalations.py` | FT-10.2 state; `host.fail_next.add("issue_comments")` | POST poll | 502 `host_error` |
| FT-10.14 | OP-5:boundary | `engine/tests/functional/test_escalations.py` | fresh app | GET inbox | `[]` |

## Context pack
- `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` — STEP-1 edit
- `engine/tests/fakes/host.py` — STEP-2 edit
- `engine/limo/incidents/apply.py` — STEP-6 edit; `engine/limo/incidents/service.py`, `engine/limo/incidents/repo.py`, `engine/limo/incidents/models.py`, `engine/limo/incidents/detect.py` — STEP-5..7 edit / read
- `engine/limo/inbox/models.py`, `engine/limo/inbox/service.py`, `engine/limo/inbox/repo.py` — STEP-8 edit / read
- `engine/limo/api/inbox_routes.py`, `engine/limo/runner/service.py` — STEP-8b edit
- `engine/limo/common/errors.py` — STEP-8 edit
- `engine/limo/hosts/issue_repo.py`, `engine/limo/common/errors.py`, `engine/limo/projects/models.py`, `engine/limo/store/db.py` — read
- `engine/limo/app.py` — STEP-9 edit
- `engine/tests/builders.py`, `engine/tests/conftest.py`, `engine/tests/fakes/llm.py`, `engine/tests/functional/test_resolver_actions.py` — read (flow pattern)

## Steps
### STEP-1 port
- file: `engine/limo/hosts/ports.py`, `engine/limo/hosts/unconfigured.py` (edit)
- do: add frozen `IssueComment(id: str, body: str, mine: bool)` and the two methods to `RepoHost`; `UnconfiguredHost` raises `HostError` for both
- verify: `cd engine && uv run python -c "import limo.hosts.unconfigured"` → exit 0

### STEP-2 fake host comments
- file: `engine/tests/fakes/host.py` (edit)
- do: `FakeIssue.comments: list[IssueComment]` (default empty); `comment_issue` (check `fail_next`, record `("comment_issue", number)`, append `IssueComment(f"k{n}", body, True)`); `issue_comments` (check `fail_next`, record, return a copy); test control `reply(number, body)` appends `IssueComment(f"k{n}", body, False)` (not recorded)
- verify: `mise run test:engine -- -k ft_8` → passed

### STEP-3 tests (test first)
- file: `engine/tests/functional/test_escalations.py` (create)
- do: one function per FT-10.1 … FT-10.14; names `test_ft_10_<k>_<behavior>`, docstring starts `"""FT-10.<k> `; shared local helpers for the flow, the two-retry setup (FT-10.1 state) and the escalated setup (FT-10.2 state)
- verify: `mise run test:engine -- -k ft_10` → FAIL (no comment / no limit)

### STEP-4 columns
- file: `engine/limo/store/migrations/012_escalations.sql` (create)
```sql
ALTER TABLE incidents ADD COLUMN ask TEXT;
ALTER TABLE incidents ADD COLUMN reply TEXT;
ALTER TABLE incidents ADD COLUMN human_input INTEGER NOT NULL DEFAULT 0;
ALTER TABLE incidents ADD COLUMN last_comment_id TEXT;
```
- verify: migrate a temp db (same command as earlier tickets) → exit 0

### STEP-5 incident repo + models
- file: `engine/limo/incidents/repo.py`, `engine/limo/incidents/models.py` (edit)
- do: `Incident` gains `id`, `human_input: bool`; `IncidentRow` gains `ask`, `reply`, `human_input: bool`, `last_comment_id`; `IncidentRow` keeps defaults so existing constructors work. Repo: `resolver_count(project_id, feature, ticket) -> int` (`resolver_run_id IS NOT NULL AND human_input = 0`); `set_ask(id, ask)`; `set_reply(id, reply, comment_id)`; `awaiting_reply(project_id, feature) -> list[IncidentRow]` (`needs_human`, `reply IS NULL`); `replied(project_id, feature) -> list[IncidentRow]` (`needs_human`, `reply IS NOT NULL`); `get(id) -> IncidentRow | None`; `escalations() -> list[tuple[IncidentRow, str, str]]` (row, project name, feature; `needs_human` and `reply IS NULL`, join projects); `blocking_tickets` = `open` or (`needs_human` and `reply IS NULL`)
- verify: `cd engine && uv run python -c "import limo.incidents.repo"` → exit 0

### STEP-6 escalation comment (revision 1: verify r0 — reason passed in)
- file: `engine/limo/incidents/apply.py` (edit)
- do:
  - change the signature to `apply(self, ctx: ApplyContext, action: dict[str, Any] | None, run_failed: bool = False)`
  - replace the existing `self._escalate(ctx)` call in `apply` with:
```python
            if action is not None and action.get("type") == "escalate":
                summary, ask = str(action.get("summary", "")), str(action.get("ask", ""))
            else:
                reason = "resolver run failed" if run_failed else (
                    "invalid action" if action is None else "action could not be applied"
                )
                summary = f"Resolver could not act ({reason})"
                ask = f"What should Limo do with {ctx.incident.ticket}?"
            self.escalate(ctx, summary, ask)
```
  - rename `_escalate(self, ctx)` to public `escalate(self, ctx, summary: str, ask: str)`: after adding the label, call `self._host.comment_issue(hp, issue.number, f"Limo needs a human.\n\n{summary}\n\nQuestion: {ask}")`, then `self._repo.set_ask(ctx.incident.id, ask)`
- verify: `cd engine && uv run python -c "import limo.incidents.apply"` → exit 0

### STEP-7 limit, replies, follow-up
- file: `engine/limo/incidents/service.py`, `engine/limo/incidents/detect.py` (edit)
- do: in `_apply`, call `self._applier.apply(ctx, action, run_failed=run.status == "failed")`. In `_open`, if `repo.resolver_count(...) >= 2` → add the row as `needs_human` (no resolver run), call `applier.escalate(ctx, f"{ticket} is still stuck after 2 resolver attempts", f"What should Limo do with {ticket}?")`, return `StepResult(run=None, reason="needs_human")`. Add `collect_replies(project, feature)`: for each `awaiting_reply` row with an issue: `host.issue_comments(...)`; first comment after `last_comment_id` (all if None) with `mine` False → `set_reply`; `HostError` → `ExternalError("host_error", …)`; the applier exposes `host`, `issues` for this (or pass them via `IncidentDeps` — add fields `host`, `issues`). In `handle`, before `_open_next`: first `replied` row → close it `resolved`, open a follow-up row (`trigger="human-reply"`, `human_input=True`, k = count + 1), bundle lines + `- human reply: <reply>`, start the resolver run, return `resolving`. Add `answer(incident_id, response) -> tuple[str, str]` (project name, feature): row missing → `NotFound("hold_not_found", …)`; not `needs_human` or already has a reply → `Conflict("hold_cleared", …)`; post `response` with `host.comment_issue`; `set_reply(id, response, None)`.
- verify: `cd engine && uv run python -c "import limo.incidents.service"` → exit 0

### STEP-8 escalations carry project, feature and time (revision 3)
- file: `engine/limo/incidents/repo.py`, `engine/limo/incidents/service.py`, `engine/limo/common/errors.py` (edit)
- do:
  - add a frozen dataclass to `incidents/repo.py`: `Escalation(row: IncidentRow, project: str, feature: str, created_at: str)`
  - `IncidentRepo.escalations()` returns `list[Escalation]`; its SELECT adds `i.created_at`; build each item as
```python
        result = []
        for r in rows:
            data = dict(r)
            project, feature, created_at = data.pop("project"), data.pop("feature"), data.pop("created_at")
            result.append(Escalation(_row(data), str(project), str(feature), str(created_at)))
        return result
```
    (`_row` accepts a plain dict as well as a row)
  - in `IncidentService.answer` replace `row, name, feature = match` with `row, name, feature = match.row, match.project, match.feature`, and the `next(...)` matcher with `next((e for e in self._repo.escalations() if e.row.id == incident_id), None)`
  - `common/errors.py`: add `class Unprocessable(LimoError): status = 422`
- verify: `cd engine && uv run python -c "import limo.incidents.service, limo.common.errors"` → exit 0

### STEP-8b inbox items, continue with a response, poll collects replies (revision 3)
- file: `engine/limo/inbox/models.py`, `engine/limo/runner/service.py`, `engine/limo/api/inbox_routes.py` (edit)
- do:
  - `inbox/models.py`: keep `Hold`; add `InboxItem(BaseModel)`: `id, project, feature, ticket: str`, `kind: Literal["budget", "escalation"]`, `reason: str`, `created_at: str`, `link: str | None = None`; add `ContinueIn(BaseModel)`: `model_config = ConfigDict(extra="forbid")`, `response: str | None = Field(default=None, min_length=1, max_length=2000)`
  - `RunnerService`: `RunnerDeps` gains `issue_repo: IssueRepo` (from `limo.hosts.issue_repo`; the existing `issues: IssueService` field stays). Add
    - `inbox() -> list[InboxItem]`: budget holds from `self._inbox.list()` → `InboxItem(**hold.model_dump(), link=None)`; escalations from `self._incidents.escalations()` (add a pass-through method `escalations()` on `IncidentService` returning the repo list) → `InboxItem(id=e.row.id, project=e.project, feature=e.feature, ticket=e.row.ticket, kind="escalation", reason=e.row.ask or "needs a human", created_at=e.created_at, link=<issue url or None>)` where the url comes from `self._issue_repo.for_feature(<project id>, e.feature).get(e.row.ticket)` (project id via `self._projects.get_by_name(e.project)`); return all items sorted by `created_at`
    - `continue_item(item_id: str, response: str | None) -> StepResult`: if `self._inbox.has(item_id)` (add `InboxService.has(hold_id) -> bool` = the repo `get` is not None) → `return self.continue_hold(item_id)`; else if `response is None` → `raise Unprocessable("response_required", "an escalation needs a response")`; else `name, feature = self._incidents.answer(item_id, response)` and `return self.step(name, feature)`
    - in `poll`, after `result = self._shipping.poll(project, feature)`: `self._incidents.collect_replies(project, feature)`; return `result`
  - `api/inbox_routes.py`: `inbox_router(runner: RunnerService)`: `GET /api/inbox` → `list[InboxItem]` = `runner.inbox()`; `POST /api/inbox/{item_id}/continue` with `body: ContinueIn | None = None` → `runner.continue_item(item_id, body.response if body else None)`
- also edit: `engine/limo/inbox/service.py` (add `has`)
- verify: `cd engine && uv run python -c "import limo.api.inbox_routes"` → exit 0

### STEP-9 wiring
- file: `engine/limo/app.py` (edit)
- do: pass `host`, `IssueRepo(db)` and `ProjectRepo(db)` into `IncidentDeps` (fields added in STEP-7); add `issue_repo=IssueRepo(db)` to `RunnerDeps`; call `inbox_router(runner)`
- verify: `mise run test:engine` → all passed

### STEP-10 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fix rounds), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

### STEP-11 unknown ids are 404 before the response check (revision 5)
- file: `engine/limo/runner/service.py` (edit), `engine/limo/incidents/service.py` (edit)
- do: add `IncidentService.exists(incident_id: str) -> bool` (= `self._repo.get(incident_id) is not None`). In `RunnerService.continue_item`, right after the hold branch, add `if not self._incidents.exists(item_id): raise NotFound("hold_not_found", f"item {item_id} not found")` before the `response is None` check; change nothing else
- verify: `mise run test:engine` → all passed

### STEP-12 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, `mise run gates` (up to 3 fix rounds), `mise run test`; never add `# noqa`
- verify: gates exit 0; `mise run test` all passed

## Do not
- change budget hold behavior beyond listing them as `InboxItem`
- count human-reply incidents toward the limit
- add UI
- add `# noqa`

## Doc updates
- context/INDEX.md: `incidents` line — escalation comment, 2-resolve limit, replies via poll/Continue
- context/api.md: inbox items (`kind`, `link`), continue body `response`
- context/data.md: incident columns `ask`, `reply`, `human_input`, `last_comment_id`
- context/testing.md: FakeHost comments + `reply`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
