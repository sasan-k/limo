# ADR-11: Scheduler port with a concurrency setting; v1 in-process, one ticket
status: accepted
scope: runner
supersedes: none
source: NFR-7, NFR-11

<!-- ===== L2 ===== -->
## Decision
The runner asks a `Scheduler` port for slots and schedules work; v1 is an in-process scheduler (one worker thread, SQLite runs table) honoring `max_concurrent_tickets` (default 1).

## Why
NFR-7 (replaceable scheduler) and NFR-11 (scale later without code changes).

## Rules
- MUST read concurrency only from `settings.max_concurrent_tickets`; no hard-coded "one at a time"
- MUST keep run state (claim, heartbeat, finish) in the db so any scheduler can resume it
- MUST NOT let runner services import a scheduler implementation (port only)
- MUST give each active ticket its own working tree when concurrency > 1 (git worktree per ticket)

<!-- ===== L3 ===== -->
## Alternatives
- Temporal now — rejected: extra server breaks clone-and-run (DESIGN.md › Scheduler)

## Consequences
- v1 uses one workspace checkout; worktrees arrive with concurrency > 1
