---
ticket: TKT-8
incident: 1
trigger: limits
diagnosis: other
confidence: high
---
# Resolve report TKT-8 #1

## Evidence
- `work/limo/reports/TKT-8-build-r1-1.md` — STEP-2 (fake host) needs `IssueRef`, which STEP-3 defines; build stopped before any edit
- `engine/limo/hosts/ports.py` — no `IssueRef` yet

## Reasoning
Plan step order (port after fake). The fix is mechanical: swap STEP-2 and STEP-3. Not in the resolver's allowed actions (no plan edits), plan_tries = 1.

## Action
```json
{"type": "escalate", "summary": "TKT-8 plan defines IssueRef (STEP-3) after the fake that returns it (STEP-2). Fix: move the port step before the fake.", "ask": "Approve revision 2, and let the resolver do such plan-detail revisions (order, missing path, missing type; no design change) itself, once per ticket?"}
```
