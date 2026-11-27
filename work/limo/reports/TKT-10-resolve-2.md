---
ticket: TKT-10
incident: 2
trigger: limits
diagnosis: plan-detail
confidence: high
---
# Resolve report TKT-10 #2

## Evidence
- `work/limo/reports/TKT-10-build-r2-1.md` — STEP-8 needs edits in `incidents/service.py:157` (3-tuple unpack) and `common/errors.py`, not listed in its `file:`; `IncidentRepo._row` gets `project`/`feature` keys it rejects (`repo.py:85-94, 214-222`)

## Reasoning
Still plan-detail, but this ticket already used its one `replan` → escalate.

## Action
```json
{"type": "escalate", "summary": "TKT-10: 3 plan-detail stops in a row (file lists/contracts in STEP-6..8). Steps 1-7 are built; STEP-8 (inbox/continue/poll), STEP-9 (wiring), STEP-10 (gates) remain.", "ask": "Approve a revision 3 that lists every file STEP-8 touches (service.py, repo.py _row, errors.py), or let the orchestrator (Opus) finish STEP-8..10 directly?"}
```
