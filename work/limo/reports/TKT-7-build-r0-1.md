---
ticket: TKT-7
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-9
---
# Build report TKT-7

## Steps
- STEP-1 ✅ verify passed
- STEP-2 ✅ no verify (test-first setup)
- STEP-3 ✅ verify passed (expected FAIL: `create_app`/`Deps` has no `host` argument)
- STEP-4 ✅ verify passed
- STEP-5 ✅ verify passed
- STEP-6 ✅ verify passed
- STEP-7 ✅ verify passed
- STEP-8 ✅ verify passed
- STEP-9 ✅ verify passed
- STEP-10 ⛔ stopped (`mise run test:engine`: 2 failed, 85 passed)
- STEP-11 not reached
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

## Stop reason
- step: STEP-10
- problem: conflicts with code. The plan requires all engine tests to pass (73 + 14 FT-7). The existing TKT-5 tests expect `started`, but STEP-8 makes `step` ship a `review` ticket first and return `shipped`. No fix inside STEP-10 lines resolves this without changing test expectations, which the rules forbid, so no fix attempt was made.
- evidence:
  - `tests/functional/test_runner.py::test_ft_5_3_ticket_in_review_is_not_started` FAILED
  - `tests/functional/test_runner.py::test_ft_5_4_one_run_at_a_time_and_stages_in_order` FAILED
  - `tests/functional/test_runner.py:81: AssertionError: assert 'shipped' == 'started'`
  - FT-7: 14 passed (`pytest tests/functional/test_shipping.py -k ft_7`)
