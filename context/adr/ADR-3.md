# ADR-3: Single SQLite file, plain SQL, forward-only migrations
status: accepted
scope: persistence
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
All app state lives in one SQLite file (`.factory/state.db`) accessed with stdlib `sqlite3` and plain SQL; `fx` owns the `tickets` table.

## Why
Local single-user app; zero setup; `fx` already uses stdlib sqlite3; DESIGN.md puts ticket state in SQLite.

## Rules
- MUST run SQL only in `store/` repositories, parameterized
- MUST apply migrations in order at startup; forward-only
- MUST NOT alter the `tickets` table outside `scripts/fx.py`
- MUST NOT add an ORM without a new ADR

<!-- ===== L3 ===== -->
## Alternatives
- Postgres — rejected: breaks clone-and-run
- SQLAlchemy — rejected: adds a layer; schema is small

## Consequences
- one writer at a time; fine with one ticket at a time (WAL for concurrent reads)
