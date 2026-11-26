# ADR-5: Functional tests through the HTTP API with fakes only at external boundaries
status: accepted
scope: testing
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
Engine functional tests use pytest + httpx TestClient against `create_app` with a scripted LLM fake and an in-memory RepoHost fake; SQLite, git, executor and `fx` are real. UI: Vitest for components, Playwright e2e against the engine with fakes.

## Why
Matches the factory's test rules (real entry points, production setup) while keeping runs free and deterministic.

## Rules
- MUST set up state through API calls, never direct DB writes
- MUST fake only Claude API and repo hosts
- MUST put the FT id in each test (see testing.md › Naming)

<!-- ===== L3 ===== -->
## Alternatives
- Recorded real API responses (VCR) — rejected: costly to refresh, non-deterministic tool loops
