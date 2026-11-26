# ADR-1: Python FastAPI engine, React TS UI, mise tooling
status: accepted
scope: infra, ui
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
Engine in Python 3.12 + FastAPI (uv); UI in React + TypeScript + Vite + Tailwind + shadcn/ui (npm); tools and tasks via mise.

## Why
`fx` and the Anthropic SDK are Python; a typed SPA gives the live, modern UI; mise gives clone-and-run setup.

## Rules
- MUST pin tool versions in `mise.toml` and deps in `uv.lock` / `package-lock.json`
- MUST expose every dev action as a `mise run <task>`
- MUST NOT require global installs other than mise

<!-- ===== L3 ===== -->
## Alternatives
- Node/TS engine — rejected: would rewrite `fx` and lose stdlib-only scripts
- Server-rendered UI (HTMX) — rejected: live cards and editor are simpler as an SPA

## Consequences
- two toolchains (uv + npm), hidden behind mise tasks
