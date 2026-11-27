---
ticket: TKT-7
plan_revision: 2
try: 2
result: stopped
last_passed: STEP-14
---
# Build report TKT-7

## Steps
- STEP-14 ✅ verify passed (`mise run test:engine` → 87 passed; line already present, not re-added)
- STEP-15 ⛔ stopped (gates: S608 at `limo/hosts/repo.py:71` fixed once, then mypy `no-untyped-def` at `limo/hosts/repo.py:31`)
- final check: not reached

## Files changed
- `engine/limo/hosts/repo.py` (edited: removed `_COLUMNS`, column list written literally in the `open_for` SQL string; `ruff format` also ran)
- `mise run fmt` (ruff format) reformatted 2 files; not identified, both among the ticket files below
- Ticket files (created or edited, all tries): `engine/limo/api/runner_routes.py`, `engine/limo/app.py`, `engine/limo/runner/models.py`, `engine/limo/runner/service.py`, `engine/limo/runner/tickets.py`, `engine/tests/builders.py`, `engine/tests/conftest.py`, `engine/tests/functional/test_runner.py`, `work/limo/plans/TKT-7.md`, `engine/limo/hosts/` (all files), `engine/limo/runner/shipping.py`, `engine/limo/store/migrations/007_merge_requests.sql`, `engine/limo/vcs/` (all files), `engine/tests/fakes/host.py`, `engine/tests/functional/test_shipping.py`

## Stop reason
- step: STEP-15
- problem: verify fails after 1 fix
- evidence:
  - `[types] limo/hosts/repo.py:31: error: Function is missing a type annotation for one or more parameters  [no-untyped-def]`
  - Line 31 is `def _record(row) -> MrRecord:`; the S608 finding is gone.
