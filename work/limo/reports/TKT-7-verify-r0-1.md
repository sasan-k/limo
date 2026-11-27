---
ticket: TKT-7
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-7

## Results
- functional (ticket): 14/14 (build report)
- full suite: 85/87
- gates: not run (build stopped at STEP-10)
- review: skipped

## Failures & findings
### FT-5.3, FT-5.4 (TKT-5 regression)
- class: plan
- rule: n/a (full suite must stay green)
- where: engine/tests/functional/test_runner.py:67, :81
- why: step now ships `review` tickets first (SC-24); TKT-5 tests expected no step result for review tickets. The plan missed updating them
- error:
```
assert 'shipped' == 'started'
```
- fix hint: FT-5.3 expects "shipped" then "no_ready_ticket"; FT-5.4 loop skips "shipped" steps
