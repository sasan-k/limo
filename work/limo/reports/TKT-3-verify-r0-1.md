---
ticket: TKT-3
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-3

## Results
- functional (ticket): 5/7 (from build report STEP-7)
- full suite: 33/35
- gates: not run (build stopped)
- trace check: not run
- review: skipped (earlier failure)

## Failures & findings
### FT-3.3, FT-3.4
- class: plan
- rule: n/a for test failures (api.md › Errors shape)
- where: engine/tests/functional/test_agent_settings.py:38, :45
- why: tests read `r.json()["code"]`; the API returns `{"error": {"code": …}}`. The plan named the codes but not the body path, and the builder may not edit STEP-1 lines at STEP-7
- error:
```
KeyError: 'code'
```
- fix hint: add a step that changes both reads to `r.json()["error"]["code"]`, then gates
