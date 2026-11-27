---
ticket: TKT-10
plan_revision: 5
try: 1
result: done
last_passed: STEP-12
---
# Build report TKT-10

## Steps
- STEP-11 ✅ verify passed (`mise run test:engine`: 152 passed)
- STEP-12 ✅ verify passed (fixed once: 2 ruff E501 reported by `mise run fmt` on lines this ticket changed; `mise run gates` exit 0; `mise run test`: 152 passed)
- final check: ✅ lint + functional tests passed (test_escalations.py: 14 passed)

## Files changed
<!-- Every file created/edited, repo-relative. Close uses this list as the diff scope. -->
- `engine/limo/inbox/models.py` (edited)
- `engine/limo/inbox/service.py` (edited)
- `engine/limo/incidents/service.py` (edited)
- `engine/limo/runner/service.py` (edited)
- `engine/limo/api/inbox_routes.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/limo/common/errors.py` (edited)
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/limo/incidents/apply.py` (edited)
- `engine/limo/incidents/models.py` (edited)
- `engine/limo/incidents/repo.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/limo/store/migrations/012_escalations.sql` (created)
- `engine/tests/functional/test_escalations.py` (created)

## Stop reason
