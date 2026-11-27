---
ticket: TKT-19
incident: 1
trigger: limits
diagnosis: plan-detail
confidence: high
---
# Resolve report TKT-19 #1

## Evidence
- `work/limo/reports/TKT-19-build-r1-2.md` — gates fail only on jscpd: 10-line clone `engine/limo/runner/tickets.py:72-84` (`set_status`) vs `:86-98` (`retitle`)
- the plan's STEP-7 asked for `TicketBoard.retitle` "with the board env" but named no shared helper; `set_status` is TKT-7 code the builder may not touch

## Reasoning
A missing instruction in the plan (extract one private fx runner), no design change. Builds 2/2 and plan 1/1 used; first `replan` for this ticket.

## Action
```json
{"type": "replan", "fix": "Add TicketBoard._fx(ref: TicketRef, args: list[str]) -> None that runs ['fx', *args] with the board env and raises Conflict('map_invalid', ...) on failure; set_status and retitle call it. Then gates + full suite.", "source": "work/limo/reports/TKT-19-build-r1-2.md"}
```
