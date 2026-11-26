# Code Rules
<!-- Always read when writing or reviewing code. ≤ 60 lines. Each rule: one line, imperative, checkable. -->

## Paradigm
- Ports & adapters: services depend on Protocols in `ports.py`; adapters implement them (ADR-4)
- Constructor injection; all wiring in `engine/factory/app.py`; no module-level singletons or globals
- UI: function components + hooks; server state only via react-query; no global store

## Structure (SOLID as project rules)
- SRP: `routes.py` only maps HTTP ↔ service; no logic, no SQL
- OCP: new repo host / executor / agent tool = new class implementing the port; no `if host == …` branches
- DIP: `runner`, `resolver`, `cost`, `agents` service code never imports `hosts/*`, `executor/local`, `anthropic` directly
- ISP: one Protocol per capability (e.g. `IssueTracker`, `MergeRequests`, `CiStatus`), ≤ 7 methods each
- LSP: adapters raise only the port's declared errors (`HostError`, `ExecutorError`, `LlmError`)

## Reuse (DRY)
- shared helpers: `engine/factory/common/`, `ui/src/lib/` — search there first
- extract on the 3rd duplication; no speculative abstractions
- one source for status names, agent names, event types: `engine/factory/common/constants.py`; UI uses generated types
- ticket state goes through `fx` (scripts/fx.py) functions; never duplicate its SQL

## Size & complexity
- function ≤ 40 lines · file ≤ 300 lines · cyclomatic complexity ≤ 10 · params ≤ 5

## Patterns — use
- app factory `create_app(settings, deps)` so tests inject fakes (ADR-5)
- streaming Messages API calls with SDK retries; log usage per call (ADR-6)
- SQL in `store/` repositories only, parameterized (`?`)

## Patterns — avoid
- blocking calls in async routes → run sync work via `run_in_threadpool` or the runner thread
- string-built shell commands → `executor` with argv lists
- catching bare `Exception` outside the runner's top-level guard

## Naming
- python: snake_case modules/functions, PascalCase classes, tests `test_<area>.py`; TS: PascalCase components, camelCase functions
- domain names = glossary code names

## Errors · Validation · Logging
- errors: services raise typed errors from `common/errors.py`; `api` maps them per api.md › Errors
- validation: see security.md › Input
- logging: stdlib `logging`, JSON lines; never API keys, tokens, or prompt bodies at INFO

## Dependencies
- no new runtime dependency without an ADR

## Quality gates (Verify runs all; must pass)
- format/lint (incl. size & complexity): `mise run lint` (ruff check + ruff format --check with C901≤10, PLR0913; eslint + prettier)
- duplication: `mise run dup` (jscpd --threshold 0 on changed files)
- architecture rules: `mise run arch` (import-linter contracts in `engine/pyproject.toml`)
- types: `mise run types` (mypy --strict; tsc --noEmit)
