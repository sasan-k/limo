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
- `engine/limo/agents` — prompt registry, run service (tool loop, background worker), per-agent tools → `llm`, `executor` (call)
- `engine/limo/llm` — LLM port + Anthropic adapter → Claude Messages API (HTTPS)
- `engine/limo/runner` — step: ship `review` tickets, else dispatch by ticket status via `fx` (one run at a time); poll merge requests → `agents`, `hosts`, `vcs`, `executor` (fx)
- `engine/limo/hosts` — RepoHost port (open MR, auto-merge, status; issues with label `limo:<status>`; no merge), `UnconfiguredHost` default, `merge_requests` + `issues` repos; issue sync runs on each step
- `engine/limo/vcs` — git via executor: ticket branches `limo/<feature>/<ticket>`, commit (never `work/`), push
- `engine/limo/features` — intake (requirements saved to `work/<f>/requirements/`), phases architecture → spec → nfr → tickets driven by the runner
- `engine/limo/incidents` — stuck detection (question, blocked, timeout, crash, no-transition), bundles in `work/<f>/incidents/`, resolver run, action parsing; `retry` applied (others → `needs_human` until TKT-19)
- `engine/limo/budget` — default + per-ticket/agent budgets, spend check after each Claude API call → `cost` (usage sums)
- `engine/limo/inbox` — holds: tickets waiting for a human (budget now) → `store`
- `engine/limo/cost` — prices, per-call usage, run cost, project totals → `store` (file)
- `engine/limo/resolver` — incident bundle, action validation/apply → `agents`, `store`, `hosts` (call)
- `engine/limo/hosts` — RepoHost port; GitLab + GitHub adapters → host REST APIs (HTTPS)
- `engine/limo/executor` — runs commands in a workspace via `mise exec` (subprocess)
- `engine/limo/store` — SQLite; `fx` owns the `tickets` table (file)
- `ui` — React SPA → `engine/limo/api` via REST + SSE
real GitHub/GitLab adapters (TKT-18), remaining resolver actions (TKT-19) and `ui` are (planned); see layout.md.

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
