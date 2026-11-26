# Stack
<!-- Read for versions, libs, tooling. ≤ 60 lines. Single source of truth for versions. -->
<!-- Exact library versions are pinned in engine/uv.lock and ui/package-lock.json (planned). -->

## Runtime
- engine: Python 3.12, FastAPI, served by uvicorn (ADR-1)
- ui: TypeScript 5, React, Vite, Node 22 LTS (ADR-1)
- tool versions pinned in `mise.toml` (planned): python, uv, node

## Data & messaging
- SQLite 3 via stdlib `sqlite3` — app state, ticket state, runs, usage (ADR-3)
- no queue/broker; SSE for live UI updates (ADR-2)

## Key libraries
| Purpose | Library | Notes |
|---|---|---|
| http + SSE | fastapi, uvicorn | SSE via `StreamingResponse` `text/event-stream` |
| validation | pydantic v2 | request/response models, config |
| LLM | anthropic (Python SDK) | Messages API, streaming; see ADR-6 |
| repo hosts | httpx | GitLab + GitHub REST; no vendor SDKs |
| db | sqlite3 (stdlib) | plain SQL, no ORM (ADR-3) |
| ui components | tailwindcss, shadcn/ui | |
| ui data | @tanstack/react-query | REST cache; SSE events invalidate queries |
| engine tests | pytest, httpx (TestClient) | ADR-5 |
| ui tests | vitest, @testing-library/react, playwright | ADR-5 |

## Tooling
- task runner: mise — `mise run` lists tasks
- python deps: uv — add: `cd engine && uv add <pkg>`
- node deps: npm — add: `cd ui && npm i <pkg>`
- formatter / linter: ruff (format + lint), mypy; eslint, prettier, tsc
- CI: GitHub Actions `.github/workflows/ci.yml` (planned) runs `mise run gates` + `mise run test`

## Environments
- local only: `mise run up` → engine on 127.0.0.1:8700, ui on 127.0.0.1:5173 (dev) or served by engine (build)
- config: `.env` (gitignored; template `.env.example`, planned) loaded by mise; settings model `engine/factory/config.py` (planned)
- app data dir: `.factory/` (gitignored): `state.db`, `workspaces/<project>/`
