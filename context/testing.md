# Testing
<!-- Read when defining functional tests. ≤ 60 lines. -->

## Functional tests mimic production
- enter only through real production entry points: HTTP API + SSE (engine), browser (UI e2e)
- set up state only through production actions (API calls), never direct DB writes
- assert only externally observable results: responses, SSE events, state read back via the API, files in the workspace, calls recorded by fakes
- fake only external boundaries listed below; everything inside the system is real (SQLite, git, executor, fx)

## Operation matrix categories
<!-- Plan fills one cell per category for every operation. Parsed by fx.py — keep on one line. -->
categories: happy, validation, not-found, conflict, invalid-state, idempotency, boundary, external-failure
- happy: valid request succeeds, effects observable
- validation: one test per validation rule
- not-found: target missing
- conflict: duplicate / concurrent edit / version mismatch
- invalid-state: action not allowed in current status
- idempotency: same command retried → single effect
- boundary: min/max/empty values, pagination caps, size limits
- external-failure: Claude API or repo host errors/timeouts → correct status, error shape, ticket routing
(No auth categories: no auth in v1, ADR-7.)

## Harness
- engine: `engine/tests/functional/`; pytest; run one: `mise run test:engine -- -k ft_<t>_<k>`
- app under test: in-process `create_app(settings, deps)` with fakes injected; httpx `TestClient`
- isolation: fresh temp dir per test (db, workspaces, bare git remote)
- UI e2e: `ui/e2e/` Playwright; `ui/playwright.config.ts` starts `engine/tests/e2e_app.py` (fakes, temp data dir, seeded project `shop` with the cart map) on 8701 + vite on 5174; run: `mise run test:e2e`
- UI component: Vitest in `ui/tests/`; harness `ui/tests/harness.tsx` (`serveCards`, `serveApi(routes)` — GET by path, `"POST <path>"` → `{status, body}`, returns recorded calls — `renderApp`, `card`, `FakeEventSource.emit`); run one: `mise run test:ui -- -t "FT-<t>.<k>"`
- engine SSE: `client.stream("GET", "/api/events")`, read `": connected"` first, then `next_event(lines, type)` (`tests/builders.py`); set a short `sse_heartbeat_s` in the test's settings
- reference test: `engine/tests/functional/test_projects.py`; builders: `engine/tests/builders.py` (`make_git_repo`, `add_cart_project`, `start_and_wait`, `set_status`, `get_status`, `write_workspace_file`, `fx_env`); fake `stage_responder` acts as each stage agent; `make_skills_repo(root)` (git copy of `skills/` for prompt tests), `resolver_responder(skills_dir, action_text)`, `blocking_build(skills_dir, seconds)`; a restart = a second `create_app` on the same settings

## Fakes (external boundaries only)
| External system | Fake | Location |
|---|---|---|
| local `claude -p` (ADR-14) | `FakeCli` (records request + MCP config; `hold`/`release` to call the run's MCP endpoint; `result`, `fail_with`); adapter contract test with `tests/fakes/fake_claude.py`; tests default to backend `api` (`conftest.py`) | `engine/tests/fakes/cli.py` |
| Claude Messages API | `FakeLlm` (script, repeat, fail_with; records requests; echoes request model), helpers `tool_use(…, usage=)`, `final`, `final_with(usage)` | `engine/tests/fakes/llm.py` |
| GitLab / GitHub | `FakeHost` (MRs: approve, request_changes, merge via real git on the bare repo; issues: titles, status + extra labels, comments (`reply(n, body)` = human); fail_next; records calls) | `engine/tests/fakes/host.py` |
| git remote | real local bare repo (not a fake) | per-test temp dir |
| GitHub / GitLab HTTP (adapter contract) | respx routes + JSON fixtures, both hosts (ADR-12) | `engine/tests/contract/` |

## Test data
- builders: `engine/tests/builders.py` — tiny target project (context/, work/, map.yaml) reused by tests
- no shared mutable fixtures between tests

## Naming
- python: `def test_ft_3_1_<behavior>():` with docstring starting `"""FT-3.1 …` (trace-check greps `FT-3.1`)
- Playwright/Vitest: `test("FT-3.1 <behavior>")`

## Other suites
- unit: `engine/tests/unit/`, `ui/tests/` — optional, plan decides
- full suite: `mise run test` — must stay green
