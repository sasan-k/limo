---
ticket: TKT-10
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-5
---
# Build report TKT-10

## Steps
- STEP-1 ✅ verify passed
- STEP-2 ✅ verify passed
- STEP-3 ✅ verify passed (FAIL as expected: 10 of 14 FT tests fail; FT-10.6, 10.8, 10.10, 10.14 pass before the feature exists)
- STEP-4 ✅ verify passed
- STEP-5 ✅ verify passed (import repo; repo import fixed for ruff order later in STEP-10)
- STEP-6 ⛔ stopped
- final check: not reached

## Files changed
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/tests/functional/test_escalations.py` (created)
- `engine/limo/store/migrations/012_escalations.sql` (created)
- `engine/limo/incidents/models.py` (edited)
- `engine/limo/incidents/repo.py` (edited)

## Stop reason
- step: STEP-6
- problem: instruction conflicts with code. STEP-6 needs apply() to write "resolver run failed" vs "invalid action" vs "action could not be applied", but apply(ctx, action) receives only the action; the failed-run flag is known only in IncidentService._apply, which is a STEP-7 file.
- evidence: `engine/limo/incidents/service.py:70` `action = None if failed else parse_action(run.output)`; `engine/limo/incidents/apply.py:38` `def apply(self, ctx, action)`
