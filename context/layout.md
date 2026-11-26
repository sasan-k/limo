# Layout
<!-- Read when locating code. ≤ 60 lines. Paths are repo-relative. (planned) = not created yet. -->

## Tree
```
skills/<agent>/SKILL.md + templates/   # agent prompts + reference files (edited from the UI)
scripts/fx.py                          # ticket state + checks CLI (stdlib only)
engine/                                # (planned) Python package `factory`, pyproject.toml, uv.lock
  factory/{api,runner,agents,resolver,hosts,executor,store,cost}/
  factory/app.py  factory/config.py
  tests/functional/  tests/fakes/  tests/unit/
ui/                                    # (planned) React SPA
  src/{pages,components,api,lib}/  tests/  e2e/
context/  work/                        # factory artifacts for this app (it is its own target project)
mise.toml  .env.example                # (planned) tools, tasks, config template
```

## Module anatomy (engine/factory/<module>/)
- `ports.py` — Protocols the module depends on or exposes (only where an adapter exists)
- `service.py` — use cases; pure logic + calls to ports
- `<adapter>.py` — implementations (e.g. `hosts/gitlab.py`, `executor/local.py`)
- `routes.py` — only in `api/`: HTTP ↔ service mapping
- `models.py` — pydantic models for this module

## Where to put new things
| Adding a… | Goes in | Copy the pattern from |
|---|---|---|
| endpoint | `engine/factory/api/<area>_routes.py` | first endpoint ticket's file (planned) |
| SSE event type | `engine/factory/api/events.py` | (planned) |
| domain logic | `engine/factory/<module>/service.py` | (planned) |
| port + adapter | `engine/factory/<module>/ports.py` + `<adapter>.py` | `hosts/` (planned) |
| agent tool | `engine/factory/agents/tools/<tool>.py` | (planned) |
| table / migration | `engine/factory/store/migrations/NNN_<name>.sql` | (planned) |
| functional test | `engine/tests/functional/test_<area>.py` | (planned) |
| fake | `engine/tests/fakes/<system>.py` | (planned) |
| UI page | `ui/src/pages/<Page>.tsx` | (planned) |
| UI component | `ui/src/components/<Name>.tsx` | shadcn/ui generated components |

## Wiring
- `engine/factory/app.py` (planned) — app factory `create_app(settings, deps)`: builds adapters, injects into services, mounts routers
- `engine/factory/agents/registry.py` (planned) — agent → prompt path, model, tool allowlist
- `ui/src/main.tsx` (planned) — router + query client

## Do not touch
- `ui/src/components/ui/` (planned) — shadcn/ui generated; regenerate instead of editing
- `.factory/` — runtime data, never committed
