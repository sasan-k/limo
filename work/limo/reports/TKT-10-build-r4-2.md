---
ticket: TKT-10
plan_revision: 4
try: 2
result: stopped
last_passed: STEP-8b
---
# Build report TKT-10

## Steps
- STEP-8b ✅ verify passed (`import limo.api.inbox_routes` exit 0)
- STEP-9 ⛔ stopped (verify `mise run test:engine` → 1 failed, 151 passed)
- final check: not reached

## Files changed
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
- step: STEP-9
- problem: conflicts with code. STEP-8b `continue_item` checks `response is None` before the id lookup, so an unknown id with no body returns 422 `response_required` instead of 404.
- evidence: `tests/functional/test_budget.py:198` `test_ft_17_13_continue_not_found_and_twice`: `assert 422 == 404` on `POST /api/inbox/nope/continue` (no body). Other 14 escalation tests pass.
- note: STEP-8b `do:` did not list `engine/limo/incidents/service.py`, but its inbox() text needs `IncidentService.escalations()`. I added that method (plus the `Escalation` import) and did not treat it as a stop.
