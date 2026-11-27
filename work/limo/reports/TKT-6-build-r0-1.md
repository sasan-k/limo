---
ticket: TKT-6
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-8
---
# Build report TKT-6

## Steps
- STEP-1 ✅ verify passed (13 FT-6 tests fail on 404)
- STEP-2 ✅ verify passed (migration applies)
- STEP-3 ✅ verify passed (import ok)
- STEP-4 ✅ verify passed (87 earlier tests pass)
- STEP-5 ✅ verify passed (ft_1: 27 passed)
- STEP-6 ✅ verify passed (import ok)
- STEP-7 ✅ verify passed (import ok)
- STEP-8 ✅ verify passed (import ok)
- STEP-9 ⛔ verify fails: `mise run test:engine` → 14 failed, 86 passed
- final check: not reached

## Files changed
- `engine/tests/builders.py` (edited)
- `engine/tests/functional/test_features.py` (created)
- `engine/limo/store/migrations/008_features.sql` (created)
- `engine/limo/features/__init__.py` (created)
- `engine/limo/features/models.py` (created)
- `engine/limo/features/repo.py` (created)
- `engine/limo/features/service.py` (created)
- `engine/limo/features/phases.py` (created)
- `engine/limo/api/features_routes.py` (created)
- `engine/limo/agents/models.py` (edited)
- `engine/limo/agents/repo.py` (edited)
- `engine/limo/agents/service.py` (edited)
- `engine/limo/projects/service.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/runner/models.py` (edited)
- `engine/limo/runner/service.py` (edited)
- `engine/limo/app.py` (edited)

## Stop reason
- step: STEP-9
- problem: conflicts with code (STEP-5 `work/` exclude breaks existing ship; plan Do-not forbids changing shipping; the fix would need STEP-5 lines)
- evidence: with `_exclude_work` active, POST `/api/projects/shop/features/cart/step` after drive_to_review → 502 `{"error":{"code":"git_failed","message":"git command failed"}}`; with `_exclude_work` stubbed to a no-op → 200 `{"run":null,"reason":"shipped"}`. Suite: 14 failed (test_ft_6_5, test_ft_5_3, test_ft_5_4, test_ft_7_1..7_9, 7_12, 7_14), 86 passed.
- note: `PhaseAction.reason` also includes `run_active` (for a queued/running phase run), beyond the plan's literal list.
