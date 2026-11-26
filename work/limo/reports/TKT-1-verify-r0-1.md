---
ticket: TKT-1
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-1

## Results
- functional (ticket): 13/13 (from build report STEP-14)
- full suite: not run (build stopped)
- gates: lint ❌ · duplication ✅ · architecture ✅ · types ✅
- trace check: not run (build stopped)
- review: skipped (earlier failure)

## Failures & findings
### gate: lint (ruff format --check)
- class: plan
- rule: code-rules.md › Quality gates
- where: engine/tests/functional/test_agents.py:16
- why: the plan never runs the formatter; hand-wrapping lines to fix E501 cannot reliably satisfy `ruff format --check`
- error:
```
tests/functional/test_agents.py:16:24 File would be reformatted
1 file would be reformatted, 27 files already formatted
```
- fix hint: add a `fmt` mise task (`ruff format .` + `ruff check --fix .`) and run it in STEP-15 before `mise run gates`
