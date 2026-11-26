# ADR-10: Executor runs argv commands via `mise exec` in the workspace
status: accepted
scope: agents, infra
supersedes: none
source: NFR-5

<!-- ===== L2 ===== -->
## Decision
All agent and runner commands go through the `Executor` port; the v1 `LocalExecutor` runs `mise exec -- <argv>` with cwd = the workspace, a timeout, and a clean env.

## Why
NFR-5: one choke point for commands; a project's own `mise.toml` supplies its tools; a container executor can replace it later.

## Rules
- MUST pass commands as argv lists; never `shell=True`
- MUST set cwd inside the workspace and a timeout from settings
- MUST NOT call `subprocess` outside `executor/` (import-linter contract); git calls also go through the executor
- MUST capture stdout/stderr truncated to the payload limits in performance.md

<!-- ===== L3 ===== -->
## Alternatives
- Direct subprocess per module — rejected: no single place for timeouts, env, audit
