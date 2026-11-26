# Stack
<!-- Read for versions, libs, tooling. ≤ 60 lines. Single source of truth for versions. -->

## Runtime
- language: <name version>
- runtime: <name version>
- framework: <name version>

## Data & messaging
- <db/cache/queue name version> — used for <what>

## Key libraries
<!-- only libs a planner must know to write code; not the full lockfile -->
| Purpose | Library | Version | Notes |
|---|---|---|---|
| http | <lib> | <v> | |
| validation | <lib> | <v> | |
| orm/db | <lib> | <v> | |
| test runner | <lib> | <v> | |

## Tooling
- package manager: <name> — add dep: `<cmd>`
- formatter / linter: <names>
- CI: <where, what runs>

## Environments
- local: <how to run, e.g. `docker compose up`>
- config: <where env vars/config live> — ref: `<file>`
