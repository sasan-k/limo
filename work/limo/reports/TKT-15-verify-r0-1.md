---
ticket: TKT-15
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-15

## Results
- functional (ticket): skipped (build stopped at STEP-3)
- full suite: skipped · gates: skipped · trace check: ok · review: skipped (earlier failure)

## Failures & findings
### STEP-3 verify
- class: plan
- rule: n/a (step order)
- where: ui/tests/Cost.test.tsx:4
- why: the STEP-2 test imports `CostTotals`, which the plan only adds to `ui/src/api/types.ts` in STEP-5, so STEP-3's `tsc` cannot pass
- error:
```
tests/Cost.test.tsx(4,15): error TS2305: Module '"@/api/types"' has no exported member 'CostTotals'.
```
- fix hint: add the `CostTotals` type export to STEP-3 (types.ts in its file list); drop it from STEP-5
