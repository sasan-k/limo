---
ticket: TKT-7
plan_revision: 2
try: 1
result: stopped
last_passed: STEP-14
---
# Build report TKT-7

## Steps
- STEP-14 ✅ verify passed (`mise run test:engine`: 87 passed)
- STEP-15 ⛔ stopped (`mise run gates` exit 1 after fix attempt: lint S608 at `limo/hosts/repo.py:71`; `mise run test`: 87 passed)
- final check: not reached

## Files changed
- `engine/limo/hosts/__init__.py` (created)
- `engine/limo/hosts/ports.py` (created)
- `engine/limo/hosts/unconfigured.py` (created)
- `engine/limo/hosts/repo.py` (created; edited this run, STEP-15 fix: SQL string split across lines)
- `engine/limo/vcs/__init__.py` (created)
- `engine/limo/vcs/git.py` (created)
- `engine/limo/runner/shipping.py` (created; edited this run, STEP-14: `start_ticket` call in `ship`)
- `engine/limo/store/migrations/007_merge_requests.sql` (created)
- `engine/tests/fakes/host.py` (created)
- `engine/tests/functional/test_shipping.py` (created)
- `engine/tests/conftest.py` (edited)
- `engine/tests/builders.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/runner/models.py` (edited)
- `engine/limo/runner/service.py` (edited; edited this run, STEP-15 fix: wrapped `start_ticket` call)
- `engine/limo/api/runner_routes.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/tests/functional/test_runner.py` (edited, STEP-12: FT-5.3 ship assertions, FT-5.4 shipped skip, range 16)

## Stop reason
- step: STEP-15
- problem: verify fails after 1 fix
- evidence: `mise run gates` → `[lint] S608 Possible SQL injection vector through string-based query construction` at `engine/limo/hosts/repo.py:71` (f-string SQL with `{_COLUMNS}`); lint reports `Found 1 error.` Tests pass (87). Not fixed: the only remaining fix would change the query construction, beyond line-wrapping.
