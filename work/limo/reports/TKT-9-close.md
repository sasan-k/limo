---
ticket: TKT-9
result: done
---
# Close report TKT-9

## Applied
- context/INDEX.md, layout.md: `incidents` module
- context/api.md: incidents endpoint, step reasons
- context/data.md: `incidents`, `runs.ticket_status`, guarded finish
- context/testing.md: resolver responder
- ADRs: none proposed

## Drift (code differs from plan — code wins)
- The resolver's report lives in `runs.output` of its run; nothing writes `reports/TKT-n-resolve-<k>.md` yet (skills/resolver says it writes it, but its allowlist has no write tool) → refresh needed in TKT-19 (runner writes the report from the output)
