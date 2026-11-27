---
ticket: TKT-7
incident: 2
trigger: limits
diagnosis: other
confidence: low
---
# Resolve report TKT-7 #2

## Evidence
- `engine/limo/hosts/repo.py:31` — mypy `no-untyped-def` on `def _record(row)` (gates, build r2-2)
- build r2-1 / r2-2: each try fixes one gate error and then stops on the next one (S608, then mypy) — the one-fix-per-step rule meets a gate step that reports errors one tool at a time

## Reasoning
Mechanical, but at build and plan limits and not in the resolver's action set (no plan edits). Root cause is a process gap: the final gates step needs room for several small fixes.

## Action
```json
{"type": "escalate", "summary": "TKT-7: all 87 tests pass; gates now fail only on one missing type hint (`_record(row: sqlite3.Row) -> MrRecord`). Builds keep stopping because the gates step allows one fix, while gates report errors one at a time.", "ask": "Allow the fix, and change the build rule so the final gates step may fix up to 3 reported issues (only on lines the ticket changed)?"}
```
