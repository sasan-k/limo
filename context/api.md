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
- endpoint: (planned) first endpoint ticket
- SSE: (planned) `engine/limo/api/events.py`
