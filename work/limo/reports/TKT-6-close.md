---
ticket: TKT-6
result: done
---
# Close report TKT-6

## Applied
- context/INDEX.md, layout.md: `features` module
- context/api.md: features endpoints, `stage_failed`, run args
- context/data.md: `features`, `runs.args`
- context/security.md: `work/` exclusion + add/reset commit
- context/glossary.md: Phase
- skills/build/SKILL.md: files created/edited by the plan are always the builder's to fix
- ADRs: none proposed

## Drift (code differs from plan — code wins)
- `PhaseAction.reason` also has `run_active` (a running phase run); runner maps it to `run_active`
- commit command changed to `add -A` + `reset -- work` (TKT-7 code, revision 1)
