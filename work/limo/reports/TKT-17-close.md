---
ticket: TKT-17
result: done
---
# Close report TKT-17

## Applied
- context/INDEX.md: `budget`, `inbox` modules
- context/layout.md: module list
- context/api.md: budget + inbox endpoints
- context/data.md: budget tables, holds
- context/glossary.md: Hold
- skills/build/SKILL.md: `like:` without range / `read` files are read whole (found during this ticket)
- ADRs: none proposed

## Drift (code differs from plan — code wins)
- RunnerService kept `max_concurrent: int` and added `inbox` (5 params excl. self; ruff counts without self) instead of a RunnerConfig
- Plan revision 2 was started past the re-plan limit by the orchestrator, flagged to the user (verify r1-2)
