# <Project> — Context Index
<!-- Always read. Keep ≤ 60 lines. Facts live in the linked files, not here. -->

## System
<3–5 lines: what it does, who uses it, main entry points (HTTP API, workers, CLI…)>

## Shape
<modules/services and how they talk, one line each>
- `<module>` — <owns what> → talks to `<module>` via <REST|gRPC|events|call>

## Stack
<one line, e.g. TypeScript 5 · Node 22 · NestJS · Postgres 16 · Kafka> — details: stack.md

## Routing — read on demand
| When the ticket… | Read |
|---|---|
| writes or reviews any code | code-rules.md (always) |
| plans any ticket | security.md, performance.md (always) |
| needs to find where things live | layout.md |
| adds/changes an endpoint, message, or contract | api.md |
| adds/changes tables, fields, migrations | data.md |
| defines functional tests | testing.md |
| needs versions, libs, build/test commands | stack.md |
| uses domain terms | glossary.md |
| touches a scope listed in adr/INDEX.md | adr/ADR-n.md (L2 first) |

## Commands
- build: `<cmd>`
- test (all): `<cmd>`
- test (one): `<cmd with placeholder>`
- lint/format: `<cmd>`
- quality gates: see code-rules.md › Quality gates

## Scope tags (fixed vocabulary for ADRs and tickets)
`api` `persistence` `events` `auth` `ui` `infra` `testing` `<add project-specific>`
