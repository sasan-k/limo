---
ticket: TKT-19
plan_revision: 1
try: 2
result: stopped
last_passed: STEP-12
---
# Build report TKT-19

## Steps
- STEP-12 ✅ verify passed (`mise run test:engine`: 138 passed; from the earlier run)
- STEP-13 ⛔ stopped (`mise run fmt` ok; `mise run gates` round 1: 13 E501 fixed by wrapping; round 2: mypy 2 errors fixed; round 3 not run, jscpd clone remains)
- final check: not reached

## Files changed
- `engine/limo/incidents/repo.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/tests/functional/test_resolver_actions.py` (created)
- `scripts/fx.py` (edited)
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/limo/store/migrations/011_incident_notes.sql` (created)
- `engine/limo/agents/models.py` (edited)
- `engine/limo/agents/repo.py` (edited)
- `engine/limo/agents/service.py` (edited)
- `engine/limo/incidents/models.py` (edited)
- `engine/limo/incidents/apply.py` (created)
- `engine/limo/incidents/service.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/runner/service.py` (edited)

## Stop reason
- step: STEP-13 (format, gates, full suite)
- problem: conflicts with code: the gate's duplicate-code check (jscpd, threshold 0) reports a clone between the new `TicketBoard.retitle` and the existing `TicketBoard.set_status`; removing it needs edits to `set_status` (not a line this ticket changed)
- evidence: `engine/limo/runner/tickets.py` 90:6-100:10 (retitle) clones 76:18-86:8 (set_status), 10 lines; `ERROR: jscpd found too many duplicates (0.28%) over threshold (0%)`
