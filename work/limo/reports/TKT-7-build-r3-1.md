---
ticket: TKT-7
plan_revision: 3
try: 1
result: done
last_passed: STEP-17
---
# Build report TKT-7

## Steps
- STEP-16 ✅ verify passed (`mise run types` → Success, 62 files)
- STEP-17 ✅ verify passed (`mise run fmt`, `mise run gates` exit 0, `mise run test` → 87 passed)
- final check: ✅ lint + functional tests passed (`mise run test:engine -- -k ft_7` → 14 passed)

Run scope: `from-STEP-16`. STEP-1 to STEP-15 were not run in this try; they passed in earlier tries.

## Files changed
<!-- Every file created/edited, repo-relative. Close uses this list as the diff scope. -->
- `engine/limo/hosts/repo.py` (edited in this run: `import sqlite3` added, `_record(row: sqlite3.Row)` typed)
- `engine/limo/api/runner_routes.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/limo/runner/models.py` (edited)
- `engine/limo/runner/service.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/tests/builders.py` (edited)
- `engine/tests/conftest.py` (edited)
- `engine/tests/functional/test_runner.py` (edited)
- `engine/tests/functional/test_shipping.py` (created)
- `engine/tests/fakes/host.py` (created)
- `engine/limo/runner/shipping.py` (created)
- `engine/limo/store/migrations/007_merge_requests.sql` (created)
- `engine/limo/hosts/` (created: `__init__.py`, `ports.py`, `unconfigured.py`, `repo.py`)
- `engine/limo/vcs/` (created: `__init__.py`, `git.py`)
- `work/limo/plans/TKT-7.md` (edited; plan, not built by this run)

## Stop reason
<!-- only if stopped. Facts only, ≤ 10 lines. -->
- none (result done)
