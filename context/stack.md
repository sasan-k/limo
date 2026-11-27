# Stack
<!-- Read for versions, libs, tooling. ≤ 60 lines. Single source of truth for versions. -->
<!-- Exact library versions are pinned in engine/uv.lock and ui/package-lock.json. -->

## Runtime
- engine: Python 3.12, FastAPI, served by uvicorn (ADR-1)
- ui: TypeScript 5.9.3 (held < 6.1 for typescript-eslint, openapi-typescript), React 19.3, Vite 8.4, Tailwind 4.3 (`@tailwindcss/vite`), react-query 5.108, Node 22 LTS (ADR-1)
- ui tests: Vitest 5.1 + jsdom, Playwright 1.65 + `@axe-core/playwright`; `openapi-typescript` generates `ui/src/api/schema.d.ts`
- ui theme: shadcn preset `b3GxvZtKJ1` (theme + font, `ui/components.json`) in `ui/src/styles/theme.css`; fonts `@fontsource-variable/noto-sans`, `@fontsource-variable/jetbrains-mono` 5.3.0 (ADR-13)
- tool versions pinned in `mise.toml`: python 3.12.16, node 22.23.5, uv 0.13.10; engine `requires-python >=3.12,<3.13`

## Data & messaging
- SQLite 3 via stdlib `sqlite3` — app state, ticket state, runs, usage (ADR-3)
- no queue/broker; SSE for live UI updates (ADR-2)

## Key libraries
| Purpose | Library | Notes |
|---|---|---|
| http + SSE | fastapi, uvicorn | SSE via `StreamingResponse` `text/event-stream` |
| validation | pydantic v2 | request/response models, config |
| LLM | local `claude` CLI (Claude Code, user login) | default backend `claude-cli`, `claude -p` + stream-json; ADR-14; default models (`agent_models`): build Haiku, spec/verify/close Sonnet, others `default_model` (Opus); UI/API overrides win |
| LLM (alt) | anthropic (Python SDK) | backend `api`: Messages API, streaming; ADR-6 |
| repo hosts | httpx (runtime) | GitLab REST v4 + GitHub REST/GraphQL; no vendor SDKs; tests use respx |
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
- config: `.env` (gitignored; template `.env.example`) loaded by pydantic-settings (`LIMO_` prefix) in `engine/limo/config.py`
- app data dir: `.factory/` (gitignored): `state.db`, `workspaces/<project>/`
