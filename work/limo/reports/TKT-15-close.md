---
ticket: TKT-15
result: done
---
# Close report TKT-15

## Applied
- context/layout.md: pages Prompts, Cost; shared `Select`, `useChosenProject`
- ADR: none

## Drift (code differs from plan — code wins)
- ui/e2e/cost.spec.ts: region locator `Per agent` uses `exact: true` (plan snippet matched two regions)
