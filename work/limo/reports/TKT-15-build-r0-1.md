---
ticket: TKT-15
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-2
---
# Build report TKT-15

## Steps
- STEP-1 ✅ verify passed
- STEP-2 ✅ verify passed (expected FAIL: no button named "Cost")
- STEP-3 ⛔ stopped
- final check: not reached

## Files changed
- `engine/tests/functional/test_cost_view.py` (created)
- `ui/tests/Cost.test.tsx` (created)
- `ui/src/components/Select.tsx` (created)
- `ui/src/api/projects.ts` (created)

## Stop reason
- step: STEP-3
- problem: conflicts with code (plan ordering): STEP-3 verify `cd ui && npx tsc --noEmit` cannot pass, because `ui/tests/Cost.test.tsx` (STEP-2) imports `CostTotals` from `@/api/types`, which only STEP-5 adds to `ui/src/api/types.ts`. Fixing it needs an edit to a file STEP-3 does not name.
- evidence: `tests/Cost.test.tsx(4,15): error TS2305: Module '"@/api/types"' has no exported member 'CostTotals'.`
