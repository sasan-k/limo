---
ticket: TKT-17
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-17

## Results
- functional (ticket): not run (build stopped at STEP-1, nothing written)
- full suite / gates / trace / review: not run

## Failures & findings
### STEP-1 stop: runner step route not stated
- class: plan
- rule: n/a (plan completeness: Build reads only the context pack)
- where: work/limo/plans/TKT-17.md FT-17.5
- why: "POST runner step" without the path; the route file is not in the context pack
- error:
```
stopped: route for runner step unknown (engine/limo/api/runner_routes.py not in context pack)
```
- fix hint: state `POST /api/projects/shop/features/cart/step` and its response paths in the test notes
