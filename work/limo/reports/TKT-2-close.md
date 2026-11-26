---
ticket: TKT-2
result: done
---
# Close report TKT-2

## Applied
- context/INDEX.md: Shape — `agents` (run service, tools) and new `llm` module
- context/layout.md: module list; agent tool + fake reference files
- context/api.md: runs endpoints reference
- context/data.md: `runs`, `tool_calls` columns (attempt/heartbeat still planned)
- context/security.md: allowlist enforcement location
- context/testing.md: FakeLlm + builders
- ADRs: none proposed

## Drift (code differs from plan — code wins)
- context/layout.md still listed `factory/{…}` and `factory/app.py` from before the Limo rename → written as `limo/…`
- Agents that only report (verify, resolver) have no `write_file`; their report text is the run's `output` (stored in `runs.output`), to be written to `reports/` by the runner (TKT-5/TKT-9). Verify/resolver SKILL.md still say they write the report themselves → refresh needed when the runner lands
