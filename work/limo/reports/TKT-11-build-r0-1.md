---
ticket: TKT-11
plan_revision: 0
try: 1
result: done
last_passed: STEP-8
---
# Build report TKT-11

## Steps
- STEP-1 ✅ verify passed (6 of 7 FT-11 fail on stated reasons, e.g. KeyError 'attempt'; FT-11.4 passes as the no-reset boundary guard)
- STEP-2 ✅ verify passed (152 earlier tests pass)
- STEP-3 ✅ verify passed (FT-11.7)
- STEP-4 ✅ verify passed (ft_5 or ft_9: 28 passed)
- STEP-5 ✅ verify passed (import exit 0)
- STEP-6 ✅ verify passed (import exit 0)
- STEP-7 ✅ verify passed (FT-11: 7 passed)
- STEP-8 ✅ verify passed (fixed once: 3 E501 lines in files this ticket created; gates exit 0; full suite 159 passed)
- final check: ✅ lint + functional tests passed

## Files changed
- `engine/tests/fakes/llm.py` (edited)
- `engine/tests/builders.py` (edited)
- `engine/tests/functional/test_recovery.py` (created)
- `engine/limo/store/migrations/013_runs_interrupted.sql` (created)
- `engine/limo/agents/models.py` (edited)
- `engine/limo/agents/repo.py` (edited)
- `engine/limo/agents/service.py` (edited)
- `engine/limo/runner/tickets.py` (edited)
- `engine/limo/incidents/detect.py` (edited)
- `engine/limo/vcs/git.py` (edited)
- `engine/limo/runner/recovery.py` (created)
- `engine/limo/projects/repo.py` (edited)
- `engine/limo/app.py` (edited)
