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
- `<module>/repo.py` repositories (+ `store/db.py` migrator) are the only code that runs SQL; ticket state only via `fx` (`FX_DB` = this db, rows keyed `<project>/<feature>` via `FX_SCOPE`)

## Main entities
- `projects` — id, name (unique), git_url, host (github|gitlab), status, default_branch, workspace, created_at — `001_projects.sql`
- `tickets` — status + tries per (feature, ticket) — `scripts/fx.py`
- `runs` — id, project_id, agent, feature, ticket, status (queued|running|succeeded|failed), model, output, error, created_at, finished_at — `002_runs.sql` (attempt, heartbeat: planned)
- `usage` — one row per Messages API call: run_id, project_id, agent, feature, ticket, seq, model, 4 token kinds, cost_micros, priced — `004_cost.sql`; cost fixed when recorded (Q-7)
- `tool_calls` — run_id, seq, name, target, status (ok|error|rejected), summary, created_at — `002_runs.sql`
- `budget_defaults` (singleton), `ticket_budgets` (project_id, feature, ticket, agent '' = ticket), `holds` (open = `cleared_at` NULL) — `006_budgets_holds.sql`; budget reached = spent ≥ budget
- `incidents` — stuck event, resolver report path, applied action
- `prices` — model (PK), input/output/cache_read/cache_write micros per MTok — `004_cost.sql`; no price → cost 0, `priced = 0`
- `agent_settings` — agent (PK), model, updated_at — `003_agent_settings.sql`
- `settings` — caps, polling interval (planned)
