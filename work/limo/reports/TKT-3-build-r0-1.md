---
ticket: TKT-3
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-6
---
# Build report TKT-3

## Steps
- STEP-1 ✅ verify passed (FT-3 tests fail as expected: `model` key missing / PUT not routed)
- STEP-2 ✅ verify passed
- STEP-3 ✅ verify passed
- STEP-4 ✅ verify passed
- STEP-5 ✅ verify passed
- STEP-6 ✅ verify passed
- STEP-7 ⛔ stopped (verify `mise run test:engine` → 33 passed, 2 failed)
- STEP-8 not reached
- final check: not reached

## Files changed
- `engine/tests/functional/test_agent_settings.py` (created)
- `engine/limo/store/migrations/003_agent_settings.sql` (created)
- `engine/limo/agents/settings_repo.py` (created)
- `engine/limo/agents/agent_service.py` (created)
- `engine/limo/agents/models.py` (edited)
- `engine/limo/api/agents_routes.py` (edited)
- `engine/limo/agents/service.py` (edited)
- `engine/limo/app.py` (edited)

## Stop reason
- step: STEP-7
- problem: conflicts with code. Test assertions from STEP-1 read the error code at `r.json()["code"]`; the actual error envelope is `{"error": {"code": ...}}`. The codes match the plan (404 `agent_not_found`, 422 `validation_error`), so the mismatch is in the test assertion path, not in the app code.
- evidence:
  - `FAILED tests/functional/test_agent_settings.py::test_ft_3_3_rejects_invalid_model_bodies` (KeyError: 'code', line 38)
  - `FAILED tests/functional/test_agent_settings.py::test_ft_3_4_unknown_agent_not_found` (KeyError: 'code', line 45)
  - observed: `404 {"error":{"code":"agent_not_found",...}}`, `422 {"error":{"code":"validation_error",...}}`
- no fix attempted: the only fix would change test assertions, which the skill forbids. App code left as written in STEP-7.
