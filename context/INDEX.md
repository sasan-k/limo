# Limo — Context Index
<!-- Always read. Keep ≤ 60 lines. Facts live in the linked files, not here. -->

## System
Limo: standalone local app that runs the factory agents (architecture, spec, plan, build, verify, close, resolver)
end to end on a target project and shows them live. Single user on localhost.
Entry points: HTTP API + SSE (`engine`), web UI (`ui`), `mise` tasks, `fx` CLI (`scripts/fx.py`).

## Shape
- `skills/` — agent prompts + reference templates → loaded by `engine/limo/agents` (file read)
- `engine/limo/api` — REST + SSE → calls `runner`, `agents`, `store`, `cost` (call)
- `engine/limo/runner` — dispatch by ticket status, stuck guard, scheduler → `agents`, `resolver`, `hosts`, `store` (call)
- `engine/limo/agents` — prompt registry + Messages API loop + per-agent tools → Claude API (HTTPS), `executor` (call)
- `engine/limo/resolver` — incident bundle, action validation/apply → `agents`, `store`, `hosts` (call)
- `engine/limo/hosts` — RepoHost port; GitLab + GitHub adapters → host REST APIs (HTTPS)
- `engine/limo/executor` — runs commands in a workspace via `mise exec` (subprocess)
- `engine/limo/store` — SQLite; `fx` owns the `tickets` table (file)
- `ui` — React SPA → `engine/limo/api` via REST + SSE
`hosts`, `runner`, `resolver`, `cost` and `ui` are (planned); see layout.md.

## Stack
Python 3.12 · FastAPI · SQLite · Anthropic SDK · React + TypeScript + Vite + Tailwind + shadcn/ui · mise — details: stack.md

## Routing — read on demand
| When the ticket… | Read |
|---|---|
| writes or reviews any code | code-rules.md (always) |
| plans any ticket | security.md, performance.md (always) |
| needs to find where things live | layout.md |
| adds/changes an endpoint, SSE event, or contract | api.md |
| adds/changes tables, fields, migrations | data.md |
| defines functional tests | testing.md |
| needs versions, libs, build/test commands | stack.md |
| uses domain terms | glossary.md |
| touches a scope listed in adr/INDEX.md | adr/ADR-n.md (L2 first) |

## Commands
- setup: `mise install && mise run setup`
- run: `mise run up`
- build: `mise run build`
- test (all): `mise run test`
- test (one): `mise run test:engine -- -k ft_<t>_<k>` · UI: `mise run test:ui -- -t "FT-<t>.<k>"`
- lint/format: `mise run lint`
- quality gates: see code-rules.md › Quality gates

## Scope tags (fixed vocabulary for ADRs and tickets)
`api` `persistence` `auth` `ui` `infra` `testing` `agents` `runner` `host` `cost`
