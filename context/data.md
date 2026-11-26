# Data
<!-- Read when adding/changing tables, fields, migrations. ≤ 60 lines. -->

## Stores
- SQLite file `.factory/state.db` (path from config; passed to `fx` as `FX_DB`) — all app state (ADR-3)
- git: agent prompts in `skills/` (versioned by commits from the prompt editor); target code in workspaces
- files: per-project `context/` + `work/` inside each workspace (factory artifacts, owned by agents)

## Conventions
- table naming: snake_case plural; column naming: snake_case
- primary keys: TEXT UUIDv4, except `tickets` (feature, id) owned by `fx`
- timestamps: TEXT ISO-8601 UTC, `created_at` / `updated_at`
- soft delete: no
- money: INTEGER micro-dollars (`cost_micros`); converted to decimal string at the API edge
- tokens: INTEGER per kind (input, output, cache_read, cache_write)

## Migrations
- tool: plain SQL files applied in order at startup; version in `schema_version` table
- location: `engine/limo/store/migrations/NNN_<name>.sql`; migrator: `engine/limo/store/db.py`
- rules: forward-only; additive changes only without an ADR
- `tickets` table schema is owned by `scripts/fx.py` (CREATE IF NOT EXISTS); migrations never alter it

## Ownership
- `<module>/repo.py` repositories (+ `store/db.py` migrator) are the only code that runs SQL; ticket state only via `fx` functions

## Main entities
- `projects` — id, name (unique), git_url, host (github|gitlab), status, default_branch, workspace, created_at — `001_projects.sql`
- `tickets` — status + tries per (feature, ticket) — `scripts/fx.py`
- `runs` — id, project_id, agent, feature, ticket, status (queued|running|succeeded|failed), model, output, error, created_at, finished_at — `002_runs.sql` (attempt, heartbeat: planned)
- `usage` — tokens per Messages API call + `cost_micros`, linked to a run
- `tool_calls` — run_id, seq, name, target, status (ok|error|rejected), summary, created_at — `002_runs.sql`
- `incidents` — stuck event, resolver report path, applied action
- `prices` — per model: $/MTok for input, output, cache read, cache write (editable)
- `settings` — model per agent, caps, polling interval
