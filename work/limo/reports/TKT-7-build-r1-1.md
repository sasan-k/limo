---
ticket: TKT-7
plan_revision: 1
try: 1
result: stopped
last_passed: STEP-9
---
# Build report TKT-7

## Steps
- STEP-12 ⛔ stopped (`mise run test:engine`: 86 passed, 1 failed: test_ft_5_3_ticket_in_review_is_not_started)
- STEP-13 not reached
- final check: not reached

## Files changed
- `engine/limo/hosts/__init__.py` (created)
- `engine/limo/hosts/ports.py` (created)
- `engine/limo/hosts/unconfigured.py` (created)
- `engine/limo/hosts/repo.py` (created)
- `engine/limo/vcs/__init__.py` (created)
- `engine/limo/vcs/git.py` (created)
- `engine/limo/runner/shipping.py` (created)
- `engine/limo/store/migrations/007_merge_requests.sql` (created)
- `engine/tests/fakes/host.py` (created)
- `engine/tests/functional/test_shipping.py` (created)
- `engine/tests/conftest.py` (edited)
- `engine/tests/builders.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/runner/models.py` (edited)
- `engine/limo/runner/service.py` (edited)
- `engine/limo/api/runner_routes.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/tests/functional/test_runner.py` (edited, STEP-12: FT-5.3 ship assertions, FT-5.4 shipped skip, range 16)

## Stop reason
- step: STEP-12
- problem: conflicts with code. The STEP-12 test for FT-5.3 sets TKT-1 to `review` without a started ticket branch; the first `step` call now returns 502 instead of the expected `shipped` (200). Any fix would change the test setup or assertions, which the rules forbid, so no fix attempt was made.
- evidence: `engine/tests/functional/test_runner.py:65` `assert 502 == 200`. Response body not captured. The 502 is one of `git_failed` or `host_error`; the likely cause is `git push origin limo/cart/TKT-1` for a branch never created, but this is not verified.
