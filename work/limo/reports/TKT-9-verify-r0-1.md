---
ticket: TKT-9
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-9

## Results
- full suite: 121/122 (build report STEP-8) · gates not reached

## Failures & findings
### FT-5.2 (TKT-5 regression)
- class: plan
- rule: n/a (full suite green)
- where: engine/tests/functional/test_runner.py:53-54
- why: a blocked TKT-1 now opens an incident and starts a resolver run (SC-32); FT-5.2 asserted no run at all. SC-15 only requires that TKT-2 does not start
- error:
```
assert {...resolver run...} is None
```
- fix hint: FT-5.2 asserts the step did not start a run for TKT-2 (reason "resolving" for TKT-1 is fine)
