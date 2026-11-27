---
ticket: TKT-7
result: done
---
# Close report TKT-7

## Applied
- context/INDEX.md: runner ship/poll; `hosts`, `vcs` modules
- context/layout.md: modules + fake host
- context/api.md: step reasons, poll
- context/data.md: `merge_requests`
- context/testing.md: FakeHost
- skills/build/SKILL.md + DESIGN.md: gates step may fix up to 3 problems (human-approved)
- ADRs: none proposed

## Drift (code differs from plan — code wins)
- `ship` checks out the ticket branch before committing (revision 2)
- review comment ids follow FakeHost `c<n>`; real adapters (TKT-18) must provide stable increasing ids
