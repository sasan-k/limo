---
ticket: TKT-10
incident: 1
trigger: limits
diagnosis: plan-detail
confidence: high
---
# Resolve report TKT-10 #1

## Evidence
- `work/limo/reports/TKT-10-build-r1-1.md` — STEP-8 needs `created_at` to order escalations; STEP-5's `IncidentRepo.escalations()` returns `(IncidentRow, project, feature)` and `IncidentRow` has no `created_at` (`engine/limo/incidents/repo.py:82-94`)

## Reasoning
Missing field in the plan's contract, no design change; plan_tries 1, first replan for TKT-10.

## Action
```json
{"type": "replan", "fix": "IncidentRepo.escalations() returns (IncidentRow, project_name, feature, created_at); RunnerService.inbox() sorts all items by created_at.", "source": "work/limo/reports/TKT-10-build-r1-1.md"}
```
