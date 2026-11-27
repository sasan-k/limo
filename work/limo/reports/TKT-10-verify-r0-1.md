---
ticket: TKT-10
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-10

## Results
- not run (build stopped at STEP-6)

## Failures & findings
### STEP-6 stop: escalation reason not available in `apply`
- class: plan
- rule: n/a (plan completeness)
- where: engine/limo/incidents/apply.py `apply(ctx, action)`; failed-run flag lives in service.py `_apply`
- why: STEP-6 asks for three default reasons but `apply` cannot tell "resolver run failed" from "invalid action"
- fix hint: `apply(ctx, action, run_failed: bool)`; service passes `run.status == "failed"`
