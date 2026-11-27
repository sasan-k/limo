---
ticket: TKT-15
plan_revision: 1
try: 1
result: done
last_passed: STEP-7
---
# Build report TKT-15

## Steps
- STEP-1 (earlier run, not rerun) trusted
- STEP-2 (earlier run, not rerun) trusted
- STEP-3 ✅ verify passed (`tsc --noEmit` clean; Select.tsx and projects.ts already matched the plan)
- STEP-4 ✅ verify passed
- STEP-5 ✅ verify passed (18 UI tests)
- STEP-6 ✅ verify passed (fixed once: `exact: true` on the `Per agent` region locator, which also matched `Per agent on ticket`)
- STEP-7 ✅ verify passed (`fmt`, `gates`, `test` all pass)
- final check: ✅ lint + functional tests passed (`test:engine -k ft_15`, `test:ui -t FT-15`, `test:e2e`)

## Files changed
- `ui/src/api/types.ts` (edited)
- `ui/src/components/Select.tsx` (created)
- `ui/src/api/projects.ts` (created)
- `ui/src/pages/BoardPage.tsx` (edited)
- `ui/src/pages/PromptsPage.tsx` (edited)
- `ui/src/components/CostTable.tsx` (created)
- `ui/src/pages/CostPage.tsx` (created)
- `ui/src/api/events.ts` (edited)
- `ui/src/App.tsx` (edited)
- `ui/e2e/cost.spec.ts` (created)
- `engine/tests/functional/test_cost_view.py` (created, earlier run)
- `ui/tests/Cost.test.tsx` (created, earlier run)

## Stop reason
<!-- only if stopped. -->
