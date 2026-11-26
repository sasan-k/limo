# ADR-2: REST + JSON with SSE for live updates
status: accepted
scope: api, ui
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
UI talks to the engine over REST + JSON under `/api`; the engine pushes change notifications over one SSE stream `/api/events`.

## Why
Updates flow one way (engine → UI); SSE is simpler than WebSockets and works through plain HTTP.

## Rules
- MUST keep REST as the source of truth; SSE payloads are hints that trigger refetch
- MUST NOT send commands over SSE
- MUST use the envelope and event types in api.md

<!-- ===== L3 ===== -->
## Alternatives
- WebSockets — rejected: two-way not needed
- Polling only — rejected: cards must update within 1 s
