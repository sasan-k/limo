---
ticket: TKT-7
incident: 1
trigger: limits
diagnosis: other
confidence: low
---
# Resolve report TKT-7 #1

## Evidence
- `engine/limo/runner/shipping.py:42` — `ship` calls `commit_and_push` without checking out the ticket branch
- `engine/tests/functional/test_runner.py:62-65` — FT-5.3 puts TKT-1 in `review` without any run, so no local branch `limo/cart/TKT-1` exists → `git push -u origin limo/cart/TKT-1` fails → 502 `git_failed`

## Reasoning
A design gap in the plan (ship must ensure the branch), not transient, not a question, not a ticket wording problem → outside the resolver's allowed actions.

## Action
```json
{"type": "escalate", "summary": "TKT-7 shipping pushes a branch that may not exist locally (ticket reached review without a run). Fix: ShippingService.ship calls git.start_ticket(workspace, branch, base) before commit_and_push.", "ask": "Approve a plan revision 2 with that one-line fix?"}
```
