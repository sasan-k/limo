---
ticket: TKT-19
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-19

## Results
- full suite: 137/138 (build report STEP-10) · gates not reached

## Failures & findings
### FT-19.4 second blocked incident never opens
- class: plan
- rule: n/a (scenario SC-62: a second replan escalates)
- where: engine/limo/incidents/repo.py:68 `exists_for_run`
- why: for triggers without a run (blocked, question) the dedupe matches every earlier incident of that trigger, so a ticket blocked again after a resolved incident is never picked up. Open/needs_human incidents are already skipped via `blocking_tickets`
- error:
```
tests/functional/test_resolver_actions.py:34: assert 'started' == 'resolving'
```
- fix hint: `exists_for_run` returns False when `run_id is None`
