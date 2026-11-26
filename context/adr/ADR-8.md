# ADR-8: mise tasks are the only developer interface
status: accepted
scope: infra
supersedes: none
source: NFR-1, NFR-2

<!-- ===== L2 ===== -->
## Decision
A fresh clone needs only mise and git: `mise install && mise run setup && mise run up`. Every developer and CI action is a described mise task.

## Why
NFR-1 (clone-and-run in 3 commands, ≤ 10 min) and NFR-2 (every task listed with a description).

## Rules
- MUST give every task in `mise.toml` a `description`
- MUST keep `mise run setup` idempotent (safe to rerun)
- MUST run CI through the same tasks (`mise run gates`, `mise run test`)
- MUST NOT require tools outside `mise.toml` (no global pip/npm installs, no Docker)

<!-- ===== L3 ===== -->
## Alternatives
- Makefile — rejected: does not pin tool versions
- Docker Compose — rejected: target projects need host toolchains (DESIGN.md › Run locally)

## Consequences
- a CI check asserts every task has a description (`mise tasks --json`)
