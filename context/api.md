# API & Contracts
<!-- Read when adding/changing endpoints, SSE events, or contracts. ≤ 60 lines. -->

## Style
- protocol: REST + JSON under `/api`; live updates over SSE at `/api/events` (ADR-2)
- contract source of truth: FastAPI-generated OpenAPI at `/api/openapi.json`; UI types generated from it
- versioning: none (single local client shipped together); breaking change = update UI in the same ticket

## Conventions
- naming: plural nouns, kebab-case paths (`/api/agents`, `/api/tickets/{id}`), snake_case JSON fields
- ids: projects/runs UUIDv4 strings; tickets keep factory ids (`TKT-n`) scoped by project + feature
- time: ISO-8601 UTC strings
- money: USD as decimal string with 6 places (`"0.012345"`); see data.md
- pagination: `?limit=&cursor=` on run/event lists; default 50, max 200
- idempotency: commands (`POST …/start`, `…/retry`) are no-ops if already in the target state

## SSE events
- envelope: `event: <type>` + `data: {"type", "at", "project_id", "payload"}`
- types: `run.started` `run.updated` `run.finished` `ticket.changed` `incident.opened` `cost.updated` `prompt.saved`
- UI reacts by invalidating the matching REST queries; payload is a hint, REST is the truth

## Errors
- shape: `{"error": {"code": "<snake_case>", "message": "<human text>"}}`
- status mapping: validation→422, not found→404, conflict / wrong state→409, external failure (Claude/host)→502

## Auth
- none in v1: engine binds to 127.0.0.1 only (ADR-7)

## External APIs (outbound)
- Claude Messages API via anthropic SDK only (ADR-6)
- GitLab REST v4 / GitHub REST via `hosts/` adapters (httpx); tokens from config

## Reference implementations
- endpoint: `engine/limo/api/projects_routes.py`; error mapping: `engine/limo/api/errors.py`
- agents: `engine/limo/api/agents_routes.py` (`GET /api/agents`, `PUT /api/agents/{name}/model`)
- cost: `engine/limo/api/cost_routes.py` (`PUT/GET /api/prices`, `GET /api/projects/{name}/costs`)
- runner: `engine/limo/api/runner_routes.py` (`POST …/features/{feature}/step` → reason started|run_active|no_ready_ticket|shipped; `POST …/features/{feature}/poll` → merged, changes_requested)
- budgets: `engine/limo/api/budget_routes.py` (`GET/PUT /api/budgets/defaults`, `GET/PUT /api/projects/{name}/features/{feature}/tickets/{ticket}/budget`)
- inbox: `engine/limo/api/inbox_routes.py` (`GET /api/inbox` → items `kind` budget|escalation with `link`; `POST /api/inbox/{id}/continue` body `{"response"}` required for escalations → runner step; 422 `response_required`)
- features: `engine/limo/api/features_routes.py` (`POST/GET /api/projects/{name}/features`); step reason `stage_failed`; runs carry `args` (e.g. `mode=init-existing`)
- incidents: `engine/limo/api/incidents_routes.py` (`GET …/features/{feature}/incidents`); step reasons `resolving`, `resolved`, `needs_human`
- runs: `engine/limo/api/runs_routes.py` (`POST /api/projects/{name}/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/tool-calls`)
- prompts: `engine/limo/api/prompts_routes.py` (`GET /api/agents/{name}/files`; `GET|PUT …/file?path=`; `GET …/history?path=`; `POST …/rollback?path=`; 409 `version_conflict`|`git_failed`)
- runner switch: `engine/limo/api/switch_routes.py` (`GET/PUT /api/runner` `{"enabled"}`; in memory, off at start; loop in `engine/limo/runner/loop.py`)
- board: `engine/limo/api/board_routes.py` (`GET /api/projects/{name}/board` → statuses + features (`work/*/map.yaml`) with tickets from `fx board`; 409 `map_invalid`)
- agent cards: `engine/limo/api/cards_routes.py` (`GET /api/agent-cards` → 7 cards in AGENT_NAMES order; state idle|active|stuck)
- SSE: `engine/limo/api/events.py` (`GET /api/events`; first line `: connected`, `: ping` every `sse_heartbeat_s`); published now: run.started, run.updated, run.finished, cost.updated, incident.opened, prompt.saved via `EventBus` (`limo/events/bus.py`)
