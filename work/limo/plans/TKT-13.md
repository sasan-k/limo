---
ticket: TKT-13
feature: limo
scenarios: [SC-43, SC-44]
scope: [ui, api]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/ui.feature, work/limo/reqs.md#REQ-40#REQ-41, work/limo/questions.md, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/layout.md, context/glossary.md, context/adr/ADR-2.md, context/adr/ADR-13.md, work/limo/plans/TKT-12.md#Design, work/limo/plans/TKT-10.md#Design, scripts/fx.py, engine/limo/runner/tickets.py, engine/limo/runner/service.py:90-130, engine/limo/api/inbox_routes.py, engine/limo/inbox/models.py, engine/limo/api/projects_routes.py, engine/limo/projects/models.py, engine/limo/app.py, engine/tests/builders.py, engine/tests/e2e_app.py, ui/src/**, ui/tests/**, ui/e2e/**]
---
# TKT-13: Board and inbox show tickets and escalations

## Design
- where: `scripts/fx.py` (new `board` command: JSON), `runner/tickets.py` (`TicketBoard.board_json`, shared `_output`), new `limo/board/` (models + service), `api/board_routes.py`, `app.py`; `tests/e2e_app.py` seeds project `shop`. UI: nav (Agents · Board · Inbox), `BoardPage`, `TicketCard`, `InboxPage`, `InboxEntry` (Continue form), `postJson`; inbox engine endpoints already exist (TKT-10/17).
- responsibilities:
  - `fx board <work/f>` — print the feature's tickets (map.yaml merged with db state) as one JSON array
  - `TicketBoard._output(workspace, project, args) -> str` — run `fx` with scope env, map failures to `Conflict("map_invalid")`, return stdout (used by `_fx`, `titles`, `board_json`)
  - `BoardService.board(project_name) -> Board` — every `work/*/map.yaml` feature of the project's workspace, sorted by name, with its tickets
  - `BoardPage` — project select (first project by default) + one row of status columns per feature
  - `InboxEntry` — one inbox item; `ContinueForm` posts `POST /api/inbox/{id}/continue` (escalation: `{"response"}` required, budget: `{}`), then refetches `inbox` and `board`
- reuse: `TicketBoard` error mapping (`runner/tickets.py`), `load_tickets` in `fx.py`; `ProjectRepo.get_by_name`; `NotFound` (`common/errors.py`); inbox API `GET /api/inbox`, `POST /api/inbox/{id}/continue` (`api/inbox_routes.py`); UI `getJson`, `Card`/`Badge`/`Button`, `useLiveEvents`, Vitest harness (`ui/tests/harness.tsx`). Searched `limo/runner`, `limo/features`, `limo/api` for a board/ticket-list endpoint: none.
- contracts:
  - `fx board work/<f>` → stdout `[{"id", "title", "status", "depends_on": [..], "build_tries", "plan_tries"}, …]` in map order; parse errors exit 2 like other commands
  - `GET /api/projects/{name}/board` → 200 `{"project": str, "statuses": [TICKET_STATUSES in order], "features": [{"name": str, "tickets": [BoardTicket]}]}`; `BoardTicket` = `{"id", "title", "status", "depends_on": [str], "build_tries": int, "plan_tries": int}`; features = directories `work/<f>/` holding `map.yaml`, sorted; 404 `project_not_found`; 409 `map_invalid` (first line of fx stderr) if any map can't be read
  - UI query keys: `["projects"]`, `["board", <project>]`, `["inbox"]`; SSE invalidation: `run.finished`, `incident.opened` → agent-cards, board, inbox; `ticket.changed` → board
- data: none
- decisions: follows ADR-2, ADR-13 (new pages use tokens only; axe in both modes); ticket state read only through `fx` (code-rules › Reuse). `transition-colors` removed from `ui/src/components/ui/button.tsx`: axe measured a mid-transition color right after a nav click (2.65:1). No new ADR, no new dependency.

## Quality
### Security
- authn: n/a: ADR-7, 127.0.0.1 only
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: `{name}` is only looked up (unknown → 404); feature names come from workspace directories, passed to `fx` as an argv item `work/<f>` (no shell); Continue body validated by existing `ContinueIn` (1–2000 chars, extra forbid); textarea `maxLength=2000`
- injection: argv list via executor (ADR-10); React escapes all text; issue link rendered as `href` from the engine (host URL) with `rel="noreferrer"`
- data exposure / PII: board shows ids, titles, statuses, tries only
- secrets: none
- rate limit / abuse: n/a: local single user; one `fx` call per feature per board read
- audit: n/a: read-only board; Continue already audited by the runner (TKT-10)
### Performance
- queries (N+1, indexes): `fx board` = one map read + one db pass per feature (no per-ticket process)
- pagination / limits: n/a: tickets per feature are bounded by the map (tens)
- payload size: < 20 KB for typical maps
- caching: none server-side; react-query invalidated by SSE
- external calls (timeouts/retries): `fx` via executor with `command_timeout_s`
- sync vs async: sync route (FastAPI threadpool), like the other `fx`-backed routes
- NFR targets: NFR-9 → FT-13.9 (run.finished refetches the board); NFR-10 → FT-13.11 (axe in both modes)

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 board `GET /api/projects/{name}/board` | FT-13.1 | n/a: name is only looked up | FT-13.2 | n/a: read only | FT-13.3 | n/a: read only | FT-13.4 | n/a: no external call |
| OP-2 board page `ui/src/pages/BoardPage.tsx` | FT-13.5, FT-13.9 | n/a: no input | n/a: projects come from the list | n/a: read only | n/a: read only | n/a: read only | FT-13.10, FT-13.11 | n/a: shared getJson error path (FT-12.11) |
| OP-3 inbox + Continue `ui/src/components/InboxEntry.tsx` | FT-13.6, FT-13.7 | FT-13.7 | FT-13.8 | n/a: engine decides (TKT-10) | n/a: engine decides (TKT-10) | n/a: button disabled while pending; engine continue idempotent | FT-13.11 | n/a: engine errors shown as in FT-13.8 |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-13.1 | SC-43, OP-1:happy | `engine/tests/functional/test_board.py` | `add_cart_project(client, tmp_path)`; `set_status(settings, "shop", "TKT-1", "review")` | `GET /api/projects/shop/board` | 200; `body["project"] == "shop"`; `body["statuses"] == list(TICKET_STATUSES)`; `[f["name"] for f in body["features"]] == ["cart"]`; tickets by id: `TKT-1` status `review`, title `Cart shows a total`, `depends_on == []`; `TKT-2` status `todo`, `depends_on == ["TKT-1"]`, `build_tries == 0`, `plan_tries == 0` |
| FT-13.2 | OP-1:not-found | same | none | `GET /api/projects/nope/board` | 404; `body["error"]["code"] == "project_not_found"` |
| FT-13.3 | OP-1:invalid-state | same | `add_cart_project`; `write_workspace_file(settings, "shop", "work/broken/map.yaml", "feature: broken\ntickets:\n  - id: TKT-1\n    bogus: x\n")` | `GET /api/projects/shop/board` | 409; `body["error"]["code"] == "map_invalid"` |
| FT-13.4 | OP-1:boundary | same | `add_cart_project`; `write_workspace_file(…, "work/alpha/requirements/r.md", "x")` (no map); `write_workspace_file(…, "work/beta/map.yaml", BETA_MAP)` with `BETA_MAP = "feature: beta\ntickets:\n  - id: TKT-1\n    title: Beta works\n    scope: [api]\n    scenarios: [SC-1]\n    depends_on: []\n"` | `GET /api/projects/shop/board` | `[f["name"] for f in body["features"]] == ["beta", "cart"]`; beta tickets `== [{"id": "TKT-1", "title": "Beta works", "status": "todo", "depends_on": [], "build_tries": 0, "plan_tries": 0}]` |
| FT-13.5 | SC-43, OP-2:happy | `ui/tests/BoardInbox.test.tsx` | `serveApi` with `/api/projects` → `[{name: "shop"}]`, `/api/projects/shop/board` → board with TKT-1 `review`, TKT-2 `todo` depending on TKT-1 | click nav `Board` | region `cart review` holds `TKT-1`; region `cart todo` holds `TKT-2`; `ticket-TKT-2` shows `depends on TKT-1`; `ticket-TKT-1` has no `depends on` |
| FT-13.6 | SC-44, OP-3:happy | same | `/api/inbox` → escalation for TKT-1, reason `Should totals include tax?`, link `https://github.com/acme/shop/issues/7` | click nav `Inbox` | `inbox-TKT-1` shows the ask; link `Open issue` has that `href` |
| FT-13.7 | OP-3:happy, OP-3:validation | same | as FT-13.6 + `POST /api/inbox/inc-1/continue` → 200 | Continue is disabled; type `Yes, include tax` in `Response`; inbox route now `[]`; click Continue | `Nothing waiting for you.` appears; recorded POST `{method: "POST", path: "/api/inbox/inc-1/continue", body: {response: "Yes, include tax"}}` |
| FT-13.8 | OP-3:not-found | same | budget item (no link) + POST → 404 `{"error": {"code": "hold_not_found", "message": "item inc-1 not found"}}` | click Continue (no Response field shown) | text `item inc-1 not found` in the entry |
| FT-13.9 | OP-2:happy | same | board with TKT-1 `todo` | board route now TKT-1 `planned`; `FakeEventSource.last.emit("run.finished")` | TKT-1 appears in region `cart planned` without reload |
| FT-13.10 | OP-2:boundary | same | `/api/projects` → `[]` | click nav `Board` | `No projects yet.` |
| FT-13.11 | SC-43, OP-2:boundary, OP-3:boundary | `ui/e2e/board.spec.ts` | e2e engine seeded with project `shop` (cart map, all `todo`) | per mode light/dark: set `limo-theme`, reload, click `Board`, then `Inbox` | region `cart todo` holds `TKT-2`; `ticket-TKT-2` shows `depends on TKT-1`; inbox shows `Nothing waiting for you.`; axe `color-contrast` violations `[]` on both pages in both modes |

## Context pack
- `scripts/fx.py` — add `board` command
- `engine/limo/common/constants.py` — add TICKET_STATUSES
- `engine/limo/runner/tickets.py` — `_output`, `board_json`
- `engine/limo/projects/repo.py:36-50` — `get_by_name`
- `engine/limo/common/errors.py` — `NotFound`
- `engine/limo/cards/service.py` — service style to imitate
- `engine/limo/api/cards_routes.py` — router to imitate
- `engine/limo/app.py` — wiring
- `engine/pyproject.toml` — import-linter source modules
- `engine/tests/conftest.py` — fixtures
- `engine/tests/builders.py` — `add_cart_project`, `set_status`, `write_workspace_file`
- `engine/tests/functional/test_agent_cards.py:1-40` — test style to imitate
- `engine/tests/e2e_app.py` — seed a project
- `ui/src/api/client.ts`, `ui/src/api/types.ts`, `ui/src/api/events.ts` — edit
- `ui/src/components/ui/button.tsx` — drop transition
- `ui/src/App.tsx` — nav
- `ui/src/pages/AgentsPage.tsx` — page to imitate
- `ui/tests/harness.tsx` — add `serveApi`
- `ui/e2e/agents.spec.ts` — e2e style to imitate

## Steps
### STEP-1 Ticket status constant
- file: `engine/limo/common/constants.py` (edit)
- do: append `TICKET_STATUSES: tuple[str, ...] = ("todo", "planned", "built", "verified", "review", "done", "blocked", "abandoned")`
- verify: `cd engine && uv run python -c "from limo.common.constants import TICKET_STATUSES; print(len(TICKET_STATUSES))"` → `8`

### STEP-2 `fx board`
- file: `scripts/fx.py` (edit)
- do: add `json` to the first import line (`import json, os, re, sqlite3, sys`); docstring: after the `tickets` usage line add `  fx.py board      <work/feature>                 print tickets (map + state) as a JSON array`; after `cmd_tickets` add
```python
def cmd_board(work):
    _, tickets = load_tickets(work)
    keys = ["id", "title", "status", "depends_on", "build_tries", "plan_tries"]
    print(json.dumps([{k: t.get(k, [] if k == "depends_on" else "") for k in keys} for t in tickets]))
```
  and in `main` after the `tickets` branch: `elif c == "board":` → `cmd_board(rest[0])`
- verify: `FX_DB=$(mktemp -d)/s.db scripts/fx.py board work/limo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[1]['id'], d[1]['depends_on'])"` → `TKT-2 ['TKT-1']`

### STEP-3 Engine functional tests
- file: `engine/tests/functional/test_board.py` (create)
- like: `engine/tests/functional/test_agent_cards.py:1-40`
- do: FT-13.1 … FT-13.4 exactly as in the table, using the conftest `client`, `settings` fixtures and `tmp_path`. Names: `test_ft_13_1_board_groups_tickets_by_status_with_dependencies`, `test_ft_13_2_board_of_unknown_project_is_not_found`, `test_ft_13_3_invalid_map_is_map_invalid`, `test_ft_13_4_board_lists_only_features_with_a_map_sorted`; docstrings start `"""FT-13.<k> …`. Imports: `TICKET_STATUSES` from `limo.common.constants`; `add_cart_project`, `set_status`, `write_workspace_file` from `tests.builders`. Helper `_tickets(feature: dict[str, Any]) -> dict[str, dict[str, Any]]` = tickets keyed by id.
- verify: `mise run test:engine -- -k ft_13` → `FAIL: 404` (no route)

### STEP-4 TicketBoard: shared fx runner + board_json
- file: `engine/limo/runner/tickets.py` (edit)
- do: add
```python
    def _output(self, workspace: Path, project: str, args: list[str]) -> str:
        env = {"FX_DB": str(self._fx_db), "FX_SCOPE": project}
        try:
            result = self._executor.run(["fx", *args], workspace, self._timeout_s, env=env)
        except ExecutorError as e:
            raise Conflict("map_invalid", _first_line(str(e))) from e
        if result.code != 0:
            raise Conflict("map_invalid", _first_line(result.stderr))
        return result.stdout

    def board_json(self, workspace: Path, project: str, feature: str) -> str:
        return self._output(workspace, project, ["board", f"work/{feature}"])
```
  then rewrite `titles` to start with `stdout = self._output(workspace, project, ["tickets", f"work/{feature}"])` and parse `stdout.splitlines()` (drop its own env/try/code block), and rewrite `_fx` body to `self._output(ref.workspace, ref.project, args)`. `read` and `map_check` stay unchanged.
- verify: `mise run test:engine -- -k "ft_9 or ft_5"` → all pass (no behavior change)

### STEP-5 Board models
- file: `engine/limo/board/__init__.py` (create, empty), `engine/limo/board/models.py` (create)
- do:
```python
from pydantic import BaseModel


class BoardTicket(BaseModel):
    id: str
    title: str
    status: str
    depends_on: list[str]
    build_tries: int
    plan_tries: int


class BoardFeature(BaseModel):
    name: str
    tickets: list[BoardTicket]


class Board(BaseModel):
    project: str
    statuses: list[str]
    features: list[BoardFeature]
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-6 Board service
- file: `engine/limo/board/service.py` (create)
- like: `engine/limo/cards/service.py`
- do: class `BoardService(projects: ProjectRepo, tickets: TicketBoard)` with
```python
    def board(self, project_name: str) -> Board:
        project = self._projects.get_by_name(project_name)
        if project is None:
            raise NotFound("project_not_found", f"project {project_name} not found")
        workspace = Path(project.workspace)
        names = sorted(p.parent.name for p in (workspace / "work").glob("*/map.yaml"))
        features = [
            BoardFeature(
                name=name,
                tickets=[BoardTicket(**t) for t in json.loads(self._tickets.board_json(workspace, project.name, name))],
            )
            for name in names
        ]
        return Board(project=project.name, statuses=list(TICKET_STATUSES), features=features)
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-7 Board route + wiring
- file: `engine/limo/api/board_routes.py` (create), `engine/limo/app.py` (edit), `engine/pyproject.toml` (edit)
- like: `engine/limo/api/cards_routes.py`
- do: `def board_router(service: BoardService) -> APIRouter` with `@router.get("/api/projects/{name}/board", response_model=Board) def get_board(name: str) -> Board: return service.board(name)`. In `app.py` import `board_router`, `BoardService` and add after the cards router: `app.include_router(board_router(BoardService(ProjectRepo(settings.db_path), board)))` (`board` is the existing `TicketBoard` variable). In `pyproject.toml` add `"limo.board"` to `source_modules` of the ADR-4 contract.
- verify: `mise run test:engine -- -k ft_13` → 4 passed; `mise run arch` → kept

### STEP-8 Seed the e2e engine
- file: `engine/tests/e2e_app.py` (edit)
- do: `build_app(seed: bool = True) -> FastAPI`: keep `data_dir = Path(tempfile.mkdtemp(prefix="limo-e2e-"))` in a variable; after `app = create_app(settings, deps)`, `if seed: add_cart_project(TestClient(app), data_dir / "repos")` (import `TestClient` from `fastapi.testclient`, `add_cart_project` from `tests.builders`; no `with` — the app's lifespan must stay unstarted); return `app`. In `main`: `app = build_app(seed="--openapi" not in sys.argv)`. Update the module docstring: "…seeded with project `shop` (cart map from tests.builders)…".
- verify: `cd engine && uv run python -m tests.e2e_app --openapi | grep -c '"Board"'` → ≥ 1

### STEP-9 Regenerate API types
- file: `ui/src/api/schema.d.ts` (generated)
- do: `mise run gen:api`
- verify: `grep -c "BoardTicket" ui/src/api/schema.d.ts` → ≥ 1

### STEP-10 Vitest harness: generic engine stub
- file: `ui/tests/harness.tsx` (edit)
- do: insert before the `/** Renders the whole app` comment:
```tsx
export type ApiCall = { method: string; path: string; body: unknown };

/** Engine stub for any GET path in `routes.current` (else 404); records every call in the returned list.
 * A route value `{ status, body }` under key `"POST <path>"` answers that POST. */
export function serveApi(routes: { current: Record<string, unknown> }): ApiCall[] {
  const calls: ApiCall[] = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const key = method === "GET" ? path : `${method} ${path}`;
      if (!(key in routes.current)) return new Response("{}", { status: 404 });
      const value = routes.current[key];
      if (method === "GET") return new Response(JSON.stringify(value), { status: 200 });
      const reply = value as { status: number; body: unknown };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return calls;
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-11 Board and inbox component tests
- file: `ui/tests/BoardInbox.test.tsx` (create)
- do: exact contents:
```tsx
import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { Board, InboxItem } from "@/api/types";

import { FakeEventSource, renderApp, serveApi } from "./harness";

const STATUSES = ["todo", "planned", "built", "verified", "review", "done", "blocked", "abandoned"];

function board(tkt1Status: string): Board {
  return {
    project: "shop",
    statuses: STATUSES,
    features: [
      {
        name: "cart",
        tickets: [
          {
            id: "TKT-1",
            title: "Cart shows a total",
            status: tkt1Status,
            depends_on: [],
            build_tries: 0,
            plan_tries: 0,
          },
          {
            id: "TKT-2",
            title: "Cart total includes tax",
            status: "todo",
            depends_on: ["TKT-1"],
            build_tries: 0,
            plan_tries: 0,
          },
        ],
      },
    ],
  };
}

const ESCALATION: InboxItem = {
  id: "inc-1",
  project: "shop",
  feature: "cart",
  ticket: "TKT-1",
  kind: "escalation",
  reason: "Should totals include tax?",
  created_at: "2026-11-26T14:05:00+00:00",
  link: "https://github.com/acme/shop/issues/7",
};

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

function column(feature: string, status: string) {
  return within(screen.getByRole("region", { name: `${feature} ${status}` }));
}

async function open(page: string): Promise<void> {
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: page }));
}

test("FT-13.5 board puts tickets in their status column and shows dependencies", async () => {
  serveApi({ current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/board": board("review") } });
  await open("Board");
  await screen.findByRole("region", { name: "cart review" });
  expect(column("cart", "review").getByText("TKT-1")).toBeInTheDocument();
  expect(column("cart", "todo").getByText("TKT-2")).toBeInTheDocument();
  expect(within(screen.getByTestId("ticket-TKT-2")).getByText("depends on TKT-1")).toBeInTheDocument();
  expect(within(screen.getByTestId("ticket-TKT-1")).queryByText(/depends on/)).toBeNull();
});

test("FT-13.6 inbox lists an escalated ticket with its ask and issue link", async () => {
  serveApi({ current: { "/api/inbox": [ESCALATION] } });
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  expect(entry.getByText("Should totals include tax?")).toBeInTheDocument();
  expect(entry.getByRole("link", { name: "Open issue" })).toHaveAttribute("href", ESCALATION.link);
});

test("FT-13.7 Continue sends the typed response and refetches the inbox", async () => {
  const routes = {
    current: {
      "/api/inbox": [ESCALATION],
      "POST /api/inbox/inc-1/continue": { status: 200, body: { run: null, reason: "resolving" } },
    } as Record<string, unknown>,
  };
  const calls = serveApi(routes);
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  const button = entry.getByRole("button", { name: "Continue" });
  expect(button).toBeDisabled();
  fireEvent.change(entry.getByLabelText("Response"), { target: { value: "Yes, include tax" } });
  routes.current["/api/inbox"] = [];
  fireEvent.click(button);
  expect(await screen.findByText("Nothing waiting for you.")).toBeInTheDocument();
  const post = calls.find((c) => c.method === "POST");
  expect(post).toEqual({
    method: "POST",
    path: "/api/inbox/inc-1/continue",
    body: { response: "Yes, include tax" },
  });
});

test("FT-13.8 Continue shows the engine's error message", async () => {
  serveApi({
    current: {
      "/api/inbox": [{ ...ESCALATION, kind: "budget", reason: "ticket budget reached", link: null }],
      "POST /api/inbox/inc-1/continue": {
        status: 404,
        body: { error: { code: "hold_not_found", message: "item inc-1 not found" } },
      },
    },
  });
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  expect(entry.queryByLabelText("Response")).toBeNull();
  fireEvent.click(entry.getByRole("button", { name: "Continue" }));
  expect(await entry.findByText("item inc-1 not found")).toBeInTheDocument();
});

test("FT-13.9 run.finished event refetches the board without reload", async () => {
  const routes = {
    current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/board": board("todo") } as Record<
      string,
      unknown
    >,
  };
  serveApi(routes);
  await open("Board");
  await screen.findByRole("region", { name: "cart todo" });
  await vi.waitFor(() => expect(column("cart", "todo").getByText("TKT-1")).toBeInTheDocument());
  routes.current["/api/projects/shop/board"] = board("planned");
  act(() => FakeEventSource.last?.emit("run.finished"));
  await vi.waitFor(() => expect(column("cart", "planned").getByText("TKT-1")).toBeInTheDocument());
});

test("FT-13.10 board without projects says so", async () => {
  serveApi({ current: { "/api/projects": [] } });
  await open("Board");
  expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
});
```
- verify: `mise run test:ui -- -t "FT-13"` → `FAIL: no button named "Board"`

### STEP-12 API client, types, events
- file: `ui/src/api/client.ts`, `ui/src/api/types.ts`, `ui/src/api/events.ts` (edit — replace whole file)
- do: `ui/src/api/client.ts`:
```ts
/** Engine error envelope message (api.md › Errors), else the HTTP status. */
async function failure(method: string, path: string, response: Response): Promise<Error> {
  const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
  return new Error(body?.error?.message ?? `${method} ${path} failed: ${response.status}`);
}

/** GET a JSON resource from the engine; throws on a non-2xx status. */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw await failure("GET", path, response);
  return (await response.json()) as T;
}

/** POST a JSON body to the engine; throws with the engine's error message on a non-2xx status. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure("POST", path, response);
  return (await response.json()) as T;
}
```
  `ui/src/api/types.ts`:
```ts
import type { components } from "./schema";

export type AgentCard = components["schemas"]["AgentCard"];
export type LastRun = components["schemas"]["LastRun"];
export type Board = components["schemas"]["Board"];
export type BoardTicket = components["schemas"]["BoardTicket"];
export type InboxItem = components["schemas"]["InboxItem"];
export type Project = components["schemas"]["Project"];
```
  `ui/src/api/events.ts`:
```ts
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

/** SSE event type → REST queries it invalidates (api.md › SSE events; REST stays the truth). */
export const INVALIDATES: Record<string, QueryKey[]> = {
  "run.started": [["agent-cards"]],
  "run.updated": [["agent-cards"]],
  "run.finished": [["agent-cards"], ["board"], ["inbox"]],
  "incident.opened": [["agent-cards"], ["board"], ["inbox"]],
  "cost.updated": [["agent-cards"]],
  "ticket.changed": [["board"]],
};

/** Opens one EventSource on /api/events and refetches the matching queries on each event. */
export function useLiveEvents(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/events");
    for (const [type, keys] of Object.entries(INVALIDATES)) {
      source.addEventListener(type, () => {
        for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
      });
    }
    return () => source.close();
  }, [queryClient]);
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-13 Button without color transition
- file: `ui/src/components/ui/button.tsx` (edit)
- do: in the `buttonVariants` base class string delete ` transition-colors` (keep everything else)
- verify: `grep -c transition ui/src/components/ui/button.tsx` → `0`

### STEP-14 Board page
- file: `ui/src/components/TicketCard.tsx`, `ui/src/pages/BoardPage.tsx` (create)
- like: `ui/src/pages/AgentsPage.tsx`
- do: `ui/src/components/TicketCard.tsx`:
```tsx
import type { BoardTicket } from "@/api/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** One ticket on the board: id, title and the tickets it depends on (REQ-40). */
export function TicketCard({ ticket }: { ticket: BoardTicket }) {
  return (
    <Card data-testid={`ticket-${ticket.id}`} className="gap-2 py-3">
      <CardHeader className="px-3">
        <CardTitle className="text-sm">{ticket.id}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 px-3 text-sm">
        <span>{ticket.title}</span>
        {ticket.depends_on.length > 0 && (
          <CardDescription>depends on {ticket.depends_on.join(", ")}</CardDescription>
        )}
      </CardContent>
    </Card>
  );
}
```
  `ui/src/pages/BoardPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import type { Board, Project } from "@/api/types";
import { TicketCard } from "@/components/TicketCard";

function FeatureBoard({ board }: { board: Board }) {
  return (
    <>
      {board.features.map((feature) => (
        <section key={feature.name} aria-label={`feature ${feature.name}`} className="flex flex-col gap-3">
          <h2 className="font-semibold">{feature.name}</h2>
          <div className="grid auto-cols-[minmax(12rem,1fr)] grid-flow-col gap-3 overflow-x-auto">
            {board.statuses.map((status) => (
              <section
                key={status}
                aria-label={`${feature.name} ${status}`}
                className="flex flex-col gap-2 rounded-lg bg-muted p-2"
              >
                <h3 className="text-muted-foreground text-xs font-medium uppercase">{status}</h3>
                {feature.tickets
                  .filter((t) => t.status === status)
                  .map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} />
                  ))}
              </section>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

/** Tickets of every feature of one project, in one column per ticket status (REQ-40). */
export function BoardPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => getJson<Project[]>("/api/projects") });
  const [chosen, setChosen] = useState<string | null>(null);
  const project = chosen ?? projects.data?.[0]?.name ?? null;
  const board = useQuery({
    queryKey: ["board", project],
    queryFn: () => getJson<Board>(`/api/projects/${encodeURIComponent(project ?? "")}/board`),
    enabled: project !== null,
  });
  if (projects.isPending) return <p className="text-muted-foreground">Loading projects…</p>;
  if (projects.isError) return <p className="text-destructive">Could not load projects.</p>;
  if (project === null) return <p className="text-muted-foreground">No projects yet.</p>;
  return (
    <div className="flex flex-col gap-4">
      <label className="flex items-center gap-2 text-sm">
        Project
        <select
          className="rounded-md border border-border bg-background px-2 py-1"
          value={project}
          onChange={(e) => setChosen(e.target.value)}
        >
          {projects.data.map((p) => (
            <option key={p.name}>{p.name}</option>
          ))}
        </select>
      </label>
      {board.isError && <p className="text-destructive">{board.error.message}</p>}
      {board.data && <FeatureBoard board={board.data} />}
    </div>
  );
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-15 Inbox page
- file: `ui/src/components/InboxEntry.tsx`, `ui/src/pages/InboxPage.tsx` (create)
- do: `ui/src/components/InboxEntry.tsx`:
```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { postJson } from "@/api/client";
import type { InboxItem } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Continue for one item: escalations need a typed response, budget holds do not. */
function ContinueForm({ item }: { item: InboxItem }) {
  const queryClient = useQueryClient();
  const [response, setResponse] = useState("");
  const needsResponse = item.kind === "escalation";
  const send = useMutation({
    mutationFn: () =>
      postJson(`/api/inbox/${encodeURIComponent(item.id)}/continue`, needsResponse ? { response } : {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["board"] });
    },
  });
  return (
    <>
      {needsResponse && (
        <label className="flex flex-col gap-1">
          Response
          <textarea
            className="rounded-md border border-border bg-background p-2"
            value={response}
            maxLength={2000}
            onChange={(e) => setResponse(e.target.value)}
          />
        </label>
      )}
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          disabled={send.isPending || (needsResponse && response.trim() === "")}
          onClick={() => send.mutate()}
        >
          Continue
        </Button>
        {send.isError && <span className="text-destructive">{send.error.message}</span>}
      </div>
    </>
  );
}

/** One inbox item: ticket, ask, issue link, and Continue (REQ-41). */
export function InboxEntry({ item }: { item: InboxItem }) {
  return (
    <Card data-testid={`inbox-${item.ticket}`}>
      <CardHeader>
        <div className="flex flex-col gap-1">
          <CardTitle>{item.ticket}</CardTitle>
          <CardDescription>
            {item.project} / {item.feature}
          </CardDescription>
        </div>
        <Badge variant={item.kind === "escalation" ? "destructive" : "secondary"}>{item.kind}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <p>{item.reason}</p>
        {item.link && (
          <a className="text-primary underline" href={item.link} target="_blank" rel="noreferrer">
            Open issue
          </a>
        )}
        <ContinueForm item={item} />
      </CardContent>
    </Card>
  );
}
```
  `ui/src/pages/InboxPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import type { InboxItem } from "@/api/types";
import { InboxEntry } from "@/components/InboxEntry";

/** Tickets waiting for a human: escalations and budget holds (REQ-41). */
export function InboxPage() {
  const items = useQuery({ queryKey: ["inbox"], queryFn: () => getJson<InboxItem[]>("/api/inbox") });
  if (items.isPending) return <p className="text-muted-foreground">Loading inbox…</p>;
  if (items.isError) return <p className="text-destructive">Could not load the inbox.</p>;
  if (items.data.length === 0) return <p className="text-muted-foreground">Nothing waiting for you.</p>;
  return (
    <section aria-label="inbox" className="grid gap-4 lg:grid-cols-2">
      {items.data.map((item) => (
        <InboxEntry key={item.id} item={item} />
      ))}
    </section>
  );
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-16 Navigation
- file: `ui/src/App.tsx` (edit — replace whole file)
- do:
```tsx
import { useState } from "react";

import { useLiveEvents } from "@/api/events";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { AgentsPage } from "@/pages/AgentsPage";
import { BoardPage } from "@/pages/BoardPage";
import { InboxPage } from "@/pages/InboxPage";

const PAGES = { Agents: AgentsPage, Board: BoardPage, Inbox: InboxPage };
type PageName = keyof typeof PAGES;

export function App() {
  useLiveEvents();
  const [page, setPage] = useState<PageName>("Agents");
  const Page = PAGES[page];
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between gap-4 border-b border-border px-6 py-3">
        <h1 className="text-lg font-semibold">Limo</h1>
        <nav className="flex gap-1">
          {(Object.keys(PAGES) as PageName[]).map((name) => (
            <Button
              key={name}
              variant={name === page ? "default" : "ghost"}
              size="sm"
              aria-current={name === page ? "page" : undefined}
              onClick={() => setPage(name)}
            >
              {name}
            </Button>
          ))}
        </nav>
        <ThemeToggle />
      </header>
      <main className="p-6">
        <Page />
      </main>
    </div>
  );
}
```
- verify: `mise run test:ui` → 10 passed

### STEP-17 E2E board and inbox
- file: `ui/e2e/board.spec.ts` (create)
- like: `ui/e2e/agents.spec.ts`
- do:
```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-13.11 board and inbox render in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Board" }).click();
    await expect(page.getByRole("region", { name: "cart todo" }).getByText("TKT-2")).toBeVisible();
    await expect(page.getByTestId("ticket-TKT-2").getByText("depends on TKT-1")).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
    await page.getByRole("button", { name: "Inbox" }).click();
    await expect(page.getByText("Nothing waiting for you.")).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
```
- verify: `mise run test:e2e` → 3 passed

### STEP-18 Format and full gates
- file: none (format only)
- do: `mise run fmt`
- verify: `mise run gates` → all pass; `mise run test` → all suites pass

## Do not
- read or write the `tickets` table outside `fx`; parse map.yaml in the engine
- change existing inbox endpoints or models
- add npm or Python packages; add a router library
- hard-code colors (tokens only, ADR-13)

## Doc updates
- context/api.md: Reference implementations — add `- board: engine/limo/api/board_routes.py (GET /api/projects/{name}/board → statuses + features with tickets from fx board; 409 map_invalid)`
- context/layout.md: engine modules list gains `board`; Wiring/where: UI pages `AgentsPage`, `BoardPage`, `InboxPage` switched by nav state in `ui/src/App.tsx` (no router)
- context/INDEX.md: Shape — add `- engine/limo/board — project board: features in work/*/map.yaml + tickets via fx board → runner/tickets`
- context/testing.md: UI harness also `serveApi(routes)` (GET by path, `"POST <path>"` → `{status, body}`, returns recorded calls); e2e engine is seeded with project `shop` (cart map)
- context/glossary.md: none (Board already defined)
- context/code-rules.md: none
- scripts/fx.py docstring: done in STEP-2
- adr: none
- adr/INDEX.md: none
