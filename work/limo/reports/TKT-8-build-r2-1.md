---
ticket: TKT-8
plan_revision: 2
try: 1
result: done
last_passed: STEP-8
---
# Build report TKT-8

## Steps
- STEP-2 ✅ verify passed
- STEP-3 ✅ verify passed (expected FAIL: 7 failed, no issues created)
- STEP-4 ✅ verify passed
- STEP-5 ✅ verify passed
- STEP-6 ✅ verify passed (fixed once: missing `pathlib.Path` import in `issues.py`, caught on re-verify)
- STEP-7 ✅ verify passed (107 passed)
- STEP-8 ✅ verify passed (fixed: 3 E501 lint reports, one line each, in files this ticket changed)
- final check: ✅ lint + functional tests passed (`test:engine -k ft_8` 7 passed; `mise run test` 107 passed)

## Files changed
- `scripts/fx.py` (edited, earlier try)
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/tests/functional/test_issues.py` (created)
- `engine/limo/store/migrations/009_issues.sql` (created)
- `engine/limo/hosts/issue_repo.py` (created)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/hosts/issues.py` (created)
- `engine/limo/runner/service.py` (edited)
- `engine/limo/app.py` (edited)
