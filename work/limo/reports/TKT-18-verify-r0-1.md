---
ticket: TKT-18
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-18

## Results
- not run (build stopped at STEP-4)

## Failures & findings
### STEP-4 verify cannot run before STEP-5..7 exist
- class: plan
- rule: n/a (step order)
- where: work/limo/plans/TKT-18.md STEP-4..STEP-6 verifies
- why: the one contract test module imports `limo.hosts.github/gitlab/router`; running any subset fails at collection until all three exist
- fix hint: STEP-4..6 verify by import / direct call; run the contract tests once after STEP-7
