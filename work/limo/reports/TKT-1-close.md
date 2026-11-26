---
ticket: TKT-1
result: done
---
# Close report TKT-1

## Applied
- context/layout.md: engine + mise.toml no longer planned; reference files for endpoint, service, port/adapter, migration, functional test; `repo.py` added to module anatomy; app.py / registry.py exist
- context/api.md: reference endpoint + error mapping
- context/data.md: migrator path; `projects` columns; SQL lives in `<module>/repo.py`
- context/code-rules.md: SQL location rule matches code
- context/testing.md: reference test + builders
- context/stack.md: pinned tool versions; config loaded by pydantic-settings (not mise)
- context/INDEX.md: planned modules narrowed to hosts, runner, resolver, cost, ui
- ADRs: none proposed by this ticket

## Drift (code differs from plan — code wins)
- SQL location: snapshot said `store/` repositories; code (per plan) puts SQL in `projects/repo.py` → snapshot written as `<module>/repo.py`
- `.env` loading: stack.md said mise loads it; code loads it in `Settings` → snapshot updated
