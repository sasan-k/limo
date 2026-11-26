# ADR-4: Ports and adapters with constructor injection
status: accepted
scope: runner, agents, host, infra
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
Services depend on Protocols (`ports.py`); adapters (Claude API, GitLab, GitHub, local executor, scheduler) implement them and are wired in `create_app`.

## Why
DESIGN.md requires swappable hosts, executors and schedulers, and tests need fakes at external boundaries.

## Rules
- MUST define a Protocol before a second implementation or any external call
- MUST wire dependencies only in `engine/factory/app.py`
- MUST NOT import adapters or vendor SDKs from service code (import-linter contract)

<!-- ===== L3 ===== -->
## Alternatives
- DI framework — rejected: constructor injection is enough
- Direct calls with mocks via patching — rejected: brittle, hides boundaries

## Pattern
`hosts/ports.py` (planned) + `hosts/gitlab.py`, `hosts/github.py`; tests pass `tests/fakes/host.py`.
