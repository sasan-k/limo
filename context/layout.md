# Layout
<!-- Read when locating code. ≤ 60 lines. Paths are repo-relative. (planned) = not created yet. -->

## Tree
```
skills/<agent>/SKILL.md + templates/   # agent prompts + reference files (edited from the UI)
scripts/fx.py                          # ticket state + checks CLI (stdlib only)
engine/                                # Python package `limo`, pyproject.toml, uv.lock
  limo/{api,agents,llm,cost,runner,projects,executor,store,common}/   # planned: resolver, hosts
  limo/app.py  limo/config.py
  tests/functional/  tests/fakes/  tests/unit/
ui/                                    # (planned) React SPA
  src/{pages,components,api,lib}/  tests/  e2e/
context/  work/                        # factory artifacts for this app (it is its own target project)
mise.toml  .env.example                # tools, tasks, config template
```

## Module anatomy (engine/limo/<module>/)
- `ports.py` — Protocols the module depends on or exposes (only where an adapter exists)
- `service.py` — use cases; pure logic + calls to ports
- `<adapter>.py` — implementations (e.g. `hosts/gitlab.py`, `executor/local.py`)
- `routes.py` — only in `api/`: HTTP ↔ service mapping
- `models.py` — pydantic models for this module
- `repo.py` — SQL for this module's tables (only place besides `store/db.py` that runs SQL) — ref: `engine/limo/projects/repo.py`

## Where to put new things
| Adding a… | Goes in | Copy the pattern from |
|---|---|---|
| endpoint | `engine/limo/api/<area>_routes.py` | `engine/limo/api/projects_routes.py` |
| SSE event type | `engine/limo/api/events.py` | (planned) |
| domain logic | `engine/limo/<module>/service.py` | `engine/limo/projects/service.py` |
| port + adapter | `engine/limo/<module>/ports.py` + `<adapter>.py` | `engine/limo/executor/ports.py` + `local.py` |
| agent tool | `engine/limo/agents/tools.py` (handler + `TOOL_SPECS`) + `allowlists.py` | `_read_file` in `tools.py` |
| table / migration | `engine/limo/store/migrations/NNN_<name>.sql` + `<module>/repo.py` | `001_projects.sql`, `projects/repo.py` |
| functional test | `engine/tests/functional/test_<area>.py` | `engine/tests/functional/test_projects.py` |
| fake | `engine/tests/fakes/<system>.py` | `engine/tests/fakes/llm.py` |
| UI page | `ui/src/pages/<Page>.tsx` | (planned) |
| UI component | `ui/src/components/<Name>.tsx` | shadcn/ui generated components |

## Wiring
- `engine/limo/app.py` — app factory `create_app(settings, deps)`: builds adapters, injects into services, mounts routers
- `engine/limo/agents/registry.py` — agent → prompt + reference paths (model, tool allowlist: planned)
- `ui/src/main.tsx` (planned) — router + query client

## Do not touch
- `ui/src/components/ui/` (planned) — shadcn/ui generated; regenerate instead of editing
- `.factory/` — runtime data, never committed
