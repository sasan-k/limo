---
ticket: TKT-1
feature: limo
scenarios: [SC-1, SC-2]
scope: [api, persistence, agents, infra]
revision: 2  # human-approved past the re-plan limit (verify r1)
run: from-STEP-16
read: [work/limo/map.yaml, work/limo/features/projects.feature, work/limo/features/agents.feature, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/adr/INDEX.md, context/layout.md, context/api.md, context/data.md, context/stack.md, ADR-1:L2, ADR-3:L2, ADR-4:L2, ADR-5:L2, ADR-7:L2, ADR-8:L2, ADR-9:L2, ADR-10:L2, .gitignore]
---
# TKT-1: A user adds a project and sees the seven agents

## Design
- where: new repo-root `mise.toml`, `.env.example`; new `engine/` (package `limo`): `config`, `common`, `store`, `executor`, `projects`, `agents`, `api`, `app`; tests in `engine/tests/`
- responsibilities:
  - `limo.config.Settings` — reads settings from env / `.env`; derives db and workspace paths
  - `limo.common.errors` — typed errors with HTTP status (`LimoError`, `NotFound`, `Conflict`, `ExternalError`)
  - `limo.common.constants` — `AGENT_NAMES`
  - `limo.store.db` — open SQLite (WAL) and apply SQL migrations in order
  - `limo.executor.ports` / `limo.executor.local` — `Executor` port; `LocalExecutor` runs `mise exec -- <argv>`
  - `limo.projects.repo` — SQL for `projects`; `limo.projects.service.ProjectService` — add (clone) and list projects
  - `limo.agents.registry.AgentRegistry` — lists agents with prompt + reference file paths from `skills/`
  - `limo.api.errors` — maps errors to the api.md error shape; `limo.api.projects_routes` / `agents_routes` — HTTP ↔ service only
  - `limo.app.create_app(settings, deps)` — wiring; `app_from_env()` for `mise run up`
- reuse: none found (searched repo: no Python code exists outside `scripts/fx.py`, which is a CLI, not importable)
- contracts:
  - `POST /api/projects` body `{"name": str, "git_url": str, "host": "github"|"gitlab"}` → 201 `Project`
    - name: `^[a-z0-9][a-z0-9-]{0,39}$`; git_url: 1–500 chars, `^(https://|ssh://|git@|file://)\S+$`; unknown fields rejected
    - 409 `project_exists` (same name) · 502 `clone_failed` · 422 `validation_error`
  - `GET /api/projects` → 200 `[Project]` ordered by `created_at`, then `name`
  - `Project` = `{"id": uuid4 str, "name", "git_url", "host", "status": "ready", "default_branch": str, "workspace": abs path str, "created_at": ISO-8601 UTC}`
  - `GET /api/agents` → 200 `[{"name": str, "prompt": str, "references": [str]}]` in `AGENT_NAMES` order; paths repo-relative, posix
  - error body: `{"error": {"code": str, "message": str}}`
- data: migration `001_projects.sql` creates `projects`; `schema_version` table created by the migrator
- decisions: follows ADR-1, ADR-3, ADR-4, ADR-5, ADR-7, ADR-8, ADR-9, ADR-10 · no new ADR

## Quality
### Security
- authn: n/a: ADR-7, bind 127.0.0.1 (`mise run up` passes `--host 127.0.0.1`)
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: pydantic models with `extra="forbid"`, name/url patterns and max lengths; `git clone --` stops a URL being read as an option
- injection: commands only as argv lists via `Executor`; SQL only parameterized in `projects/repo.py`
- data exposure / PII: none stored; responses never include stack traces (generic handler)
- secrets: none used in this ticket; `.env.example` lists names without values; `.env` already gitignored
- rate limit / abuse: n/a: local single user
- audit: n/a: no agent runs or tool calls yet (first audit rows arrive with TKT-2)
### Performance
- queries (N+1, indexes): list = one `SELECT`; `name` has a UNIQUE index
- pagination / limits: n/a: project list is small and unpaginated per api.md (pagination is for run/event lists)
- payload size: command output truncated to 20,000 chars per stream in `LocalExecutor`
- caching: n/a: none (performance.md)
- external calls (timeouts/retries): `git clone` via executor with `settings.command_timeout_s` (600); no retries
- sync vs async: sync route handlers (FastAPI runs them in its threadpool), so a clone never blocks the event loop
- NFR targets: NFR-1, NFR-2 → `mise.toml` tasks with descriptions, checked in STEP-1

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 add project `POST /api/projects` | FT-1.1 | FT-1.2, FT-1.3, FT-1.4 | n/a: creates a new resource | FT-1.5 | n/a: no prior state to violate | n/a: a repeated add is a conflict (FT-1.5) | FT-1.6 | FT-1.7, FT-1.11 |
| OP-2 list projects `GET /api/projects` | FT-1.1 | n/a: no parameters | n/a: list endpoint | n/a: read only | n/a: read only | n/a: read only | FT-1.8 | n/a: no external call |
| OP-3 list agents `GET /api/agents` | FT-1.9 | n/a: no parameters | n/a: fixed list | n/a: read only | n/a: read only | n/a: read only | FT-1.10 | n/a: no external call |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-1.1 | SC-1, OP-1:happy, OP-2:happy | `engine/tests/functional/test_projects.py` | bare git repo "shop" with `README.md` on `main` (builder) | POST project `shop`, host `github` | 201, `status` "ready", `default_branch` "main"; GET lists exactly `shop`; `<workspace>/README.md` exists |
| FT-1.2 | OP-1:validation | `engine/tests/functional/test_projects.py` | — | POST name `Shop!` | 422, `error.code` "validation_error"; GET returns `[]` |
| FT-1.3 | OP-1:validation | `engine/tests/functional/test_projects.py` | — | POST git_url each of `-uhttps://x`, `ftp://x/y`, `""` | 422 `validation_error` each |
| FT-1.4 | OP-1:validation | `engine/tests/functional/test_projects.py` | — | POST host `bitbucket`; POST with extra field `"token": "x"` | 422 `validation_error` each |
| FT-1.5 | OP-1:conflict | `engine/tests/functional/test_projects.py` | project `shop` added | POST `shop` again | 409, `error.code` "project_exists"; GET lists one `shop` |
| FT-1.6 | OP-1:boundary | `engine/tests/functional/test_projects.py` | bare repo | POST name of 40 × `a`; POST name of 41 × `a` | 201; 422 |
| FT-1.7 | OP-1:external-failure | `engine/tests/functional/test_projects.py` | — | POST git_url `file://<tmp>/missing.git` | 502, `error.code` "clone_failed"; GET `[]`; `<data>/workspaces/shop` absent |
| FT-1.11 | OP-1:external-failure | `engine/tests/functional/test_projects.py` | empty bare repo `empty.git` (`git init --bare`, no commits) | POST project `empty` with its file URL | 502, `error.code` "clone_failed"; GET `[]`; `<data>/workspaces/empty` absent |
| FT-1.8 | OP-2:boundary | `engine/tests/functional/test_projects.py` | fresh app | GET `/api/projects` | 200 `[]` |
| FT-1.9 | SC-2, OP-3:happy | `engine/tests/functional/test_agents.py` | real `skills/` dir (default settings) | GET `/api/agents` | names exactly `architecture, spec, plan, build, verify, close, resolver`; `plan.prompt` = `skills/plan/SKILL.md`; `skills/plan/templates/plan.md` in `plan.references` |
| FT-1.10 | OP-3:boundary | `engine/tests/functional/test_agents.py` | tmp `skills/` with only `<name>/SKILL.md` for all 7 | GET `/api/agents` | 7 agents, every `references` is `[]` |

## Context pack
- `.gitignore` — confirm `.venv/`, `.env`, `.factory/` already ignored (no edit)
- `mise.toml` — STEP-15 adds the `fmt` task
- files under `engine/limo/` and `engine/tests/` — STEP-15 and STEP-19 only, and only those a gate reports
- `engine/pyproject.toml` — STEP-16
- `engine/tests/functional/test_projects.py`, `engine/tests/builders.py` — STEP-17
- `engine/limo/projects/service.py` — STEP-18
- `context/INDEX.md` — Commands section only
- all other files are created by the steps below

## Steps
### STEP-1 mise tools and tasks
- file: `mise.toml` (create)
- do: run `mise use --pin python@3.12 node@22 uv@latest` at repo root (writes `[tools]` with exact versions), then add the tasks below exactly.
```toml
[tasks.setup]
description = "Install engine dependencies"
dir = "engine"
run = "uv sync"

[tasks.up]
description = "Start the engine on 127.0.0.1:8700"
dir = "engine"
run = "uv run uvicorn limo.app:app_from_env --factory --host 127.0.0.1 --port 8700"

[tasks."test:engine"]
description = "Run engine tests; pass pytest args after --"
dir = "engine"
run = "uv run pytest"

[tasks.test]
description = "Run all test suites"
depends = ["test:engine"]

[tasks.lint]
description = "Lint and format check (ruff)"
dir = "engine"
run = ["uv run ruff check .", "uv run ruff format --check ."]

[tasks.types]
description = "Type check (mypy --strict)"
dir = "engine"
run = "uv run mypy"

[tasks.arch]
description = "Architecture import contracts (import-linter)"
dir = "engine"
run = "uv run lint-imports"

[tasks.dup]
description = "Duplicate code check (jscpd)"
dir = "engine"
run = "npx --yes jscpd@4.0.5 --threshold 0 --min-lines 10 --gitignore limo"

[tasks.gates]
description = "All quality gates"
depends = ["lint", "types", "arch", "dup"]
```
- verify: `mise tasks` → lists setup, up, test:engine, test, lint, types, arch, dup, gates, each with its description

### STEP-2 engine project
- file: `engine/pyproject.toml` (create), `engine/limo/__init__.py` (create, empty)
```toml
[project]
name = "limo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi", "uvicorn", "pydantic-settings"]

[dependency-groups]
dev = ["pytest", "httpx", "ruff", "mypy", "import-linter"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["limo"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "C90", "PLR0913", "TID251"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"subprocess".msg = "Run commands through limo.executor (ADR-10)"

[tool.ruff.lint.per-file-ignores]
"limo/executor/local.py" = ["TID251", "S603", "S607"]
"tests/**" = ["TID251", "S101", "S603", "S607"]

[tool.mypy]
strict = true
packages = ["limo"]

[tool.importlinter]
root_package = "limo"

[[tool.importlinter.contracts]]
name = "Services use ports, not adapters (ADR-4)"
type = "forbidden"
source_modules = ["limo.projects", "limo.agents", "limo.store", "limo.common"]
forbidden_modules = ["limo.executor.local", "limo.api", "limo.app"]
```
- verify: `mise run setup` → exit 0 and `engine/uv.lock` exists

### STEP-3 env template
- file: `.env.example` (create)
- do: exactly these lines (names only, no values): `ANTHROPIC_API_KEY=`, `GITHUB_TOKEN=`, `GITLAB_TOKEN=`, `LIMO_DATA_DIR=`
- verify: `git check-ignore .env engine/.venv` → prints both paths

### STEP-4 test harness
- file: `engine/tests/__init__.py`, `engine/tests/functional/__init__.py` (create, empty); `engine/tests/conftest.py`, `engine/tests/builders.py` (create)
```python
# conftest.py
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from limo.app import create_app
from limo.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", _env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
```
```python
# builders.py
import subprocess
from pathlib import Path


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_git_repo(root: Path, name: str, files: dict[str, str]) -> str:
    """Create bare repo <root>/<name>.git whose branch main holds `files`; return its file:// URL."""
    src = root / f"{name}-src"
    src.mkdir(parents=True)
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    _git("init", "-b", "main", cwd=src)
    _git("add", ".", cwd=src)
    _git("-c", "user.name=limo", "-c", "user.email=limo@example.com", "commit", "-m", "init", cwd=src)
    bare = root / f"{name}.git"
    _git("clone", "--bare", str(src), str(bare), cwd=root)
    return bare.as_uri()
```
- verify: none until STEP-5 (module `limo.app` does not exist yet)

### STEP-5 project tests (test first)
- file: `engine/tests/functional/test_projects.py` (create)
- do: one test function per FT-1.1 … FT-1.8 exactly as in the Functional tests table. Name `test_ft_1_<k>_<behavior>`, docstring starts `"""FT-1.<k> `. Use fixtures `client`, `settings`, `tmp_path` and `tests.builders.make_git_repo`. FT-1.3 and FT-1.4 use `pytest.mark.parametrize`. Error checks read `r.json()["error"]["code"]`. Workspace checks use `Path(r.json()["workspace"])` and `settings.workspaces_dir / "shop"`.
- verify: `mise run test:engine -- -k ft_1_1` → FAIL: `ModuleNotFoundError: No module named 'limo.app'`

### STEP-6 agent tests (test first)
- file: `engine/tests/functional/test_agents.py` (create)
- do: FT-1.9 uses `client`. FT-1.10 builds `tmp_path / "skills" / <name> / "SKILL.md"` for every name in `limo.common.constants.AGENT_NAMES` and its own client: `TestClient(create_app(Settings(data_dir=tmp_path / "data", skills_dir=tmp_path / "skills", _env_file=None)))`.
- verify: `mise run test:engine -- -k ft_1_9` → FAIL: `ModuleNotFoundError`

### STEP-7 errors and constants
- file: `engine/limo/common/__init__.py` (empty), `engine/limo/common/errors.py`, `engine/limo/common/constants.py` (create)
```python
# errors.py
class LimoError(Exception):
    status = 500

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(LimoError):
    status = 404


class Conflict(LimoError):
    status = 409


class ExternalError(LimoError):
    status = 502
```
- do: `constants.py`: `AGENT_NAMES: tuple[str, ...] = ("architecture", "spec", "plan", "build", "verify", "close", "resolver")`
- verify: `cd engine && uv run python -c "import limo.common.errors, limo.common.constants"` → exit 0

### STEP-8 settings
- file: `engine/limo/config.py` (create)
```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIMO_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / ".factory"
    skills_dir: Path = REPO_ROOT / "skills"
    command_timeout_s: float = 600.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"
```
- verify: `cd engine && uv run python -c "from limo.config import Settings; print(Settings(_env_file=None).skills_dir.name)"` → `skills`

### STEP-9 store
- file: `engine/limo/store/__init__.py` (empty), `engine/limo/store/db.py`, `engine/limo/store/migrations/001_projects.sql` (create)
- do: `db.py`: `connect(path: Path) -> sqlite3.Connection` (row_factory `sqlite3.Row`, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`); `migrate(path: Path) -> None`: create `schema_version (version INTEGER NOT NULL)` if missing; current = `MAX(version)` or 0; for each `migrations/NNN_*.sql` sorted by name with NNN > current: `executescript`, insert NNN, commit. `MIGRATIONS = Path(__file__).parent / "migrations"`.
```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  git_url TEXT NOT NULL,
  host TEXT NOT NULL CHECK (host IN ('github', 'gitlab')),
  status TEXT NOT NULL,
  default_branch TEXT NOT NULL,
  workspace TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; p=pathlib.Path(tempfile.mkdtemp())/'s.db'; migrate(p); migrate(p)"` → exit 0

### STEP-10 executor
- file: `engine/limo/executor/__init__.py` (empty), `engine/limo/executor/ports.py`, `engine/limo/executor/local.py` (create)
- do: `ports.py`: frozen dataclass `CommandResult(code: int, stdout: str, stderr: str)`; `class Executor(Protocol): def run(self, argv: Sequence[str], cwd: Path, timeout_s: float) -> CommandResult: ...`; `class ExecutorError(Exception)`. `local.py`: `LocalExecutor.run` calls `subprocess.run(["mise", "exec", "--", *argv], cwd=cwd, capture_output=True, text=True, timeout=timeout_s, env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}, check=False)`; `TimeoutExpired` or `OSError` → raise `ExecutorError(str(e))`; return `CommandResult` with stdout/stderr cut to the first 20,000 chars.
- verify: `cd engine && uv run python -c "from pathlib import Path; from limo.executor.local import LocalExecutor; print(LocalExecutor().run(['git','--version'], Path('.'), 30).code)"` → `0`

### STEP-11 projects
- file: `engine/limo/projects/__init__.py` (empty), `models.py`, `repo.py`, `service.py` (create)
- do:
  - `models.py`: `ProjectIn(BaseModel)` with `model_config = ConfigDict(extra="forbid")`, `name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")`, `git_url: str = Field(min_length=1, max_length=500, pattern=r"^(https://|ssh://|git@|file://)\S+$")`, `host: Literal["github", "gitlab"]`. `Project(BaseModel)` with fields per Design › contracts (`status: Literal["ready"]`).
  - `repo.py`: `ProjectRepo(db_path)`: `insert(p: Project)` (IntegrityError → `Conflict("project_exists", f"project {p.name} already exists")`), `get_by_name(name) -> Project | None`, `list_all() -> list[Project]` (`ORDER BY created_at, name`). Each method opens `connect(db_path)` and closes it.
  - `service.py`: `ProjectService(repo, executor: Executor, workspaces: Path, timeout_s: float)` with `list() -> list[Project]` and `add(data: ProjectIn) -> Project`:
    1. `repo.get_by_name` → found: `Conflict("project_exists", …)`
    2. `workspaces.mkdir(parents=True, exist_ok=True)`; `path = workspaces / data.name`
    3. run `["git", "clone", "--", data.git_url, str(path)]` in `workspaces`; `ExecutorError` or code ≠ 0 → `shutil.rmtree(path, ignore_errors=True)`, raise `ExternalError("clone_failed", "could not clone the repository")`
    4. run `["git", "rev-parse", "--abbrev-ref", "HEAD"]` in `path` → `default_branch`
    5. build `Project(id=str(uuid4()), …, status="ready", workspace=str(path), created_at=datetime.now(UTC).isoformat())`, `repo.insert`, return it
- verify: `cd engine && uv run python -c "import limo.projects.service"` → exit 0

### STEP-12 agents
- file: `engine/limo/agents/__init__.py` (empty), `models.py`, `registry.py` (create)
- do: `models.py`: `Agent(BaseModel)`: `name: str`, `prompt: str`, `references: list[str]`. `registry.py`: `AgentRegistry(skills_dir: Path)` with `list() -> list[Agent]`: for each name in `AGENT_NAMES`, `d = skills_dir / name`; `prompt` = `(d / "SKILL.md")` relative to `skills_dir.parent`, `.as_posix()`; `references` = sorted posix paths (relative to `skills_dir.parent`) of all files under `d / "templates"` (recursive), `[]` if that dir is missing.
- verify: `cd engine && uv run python -c "from limo.agents.registry import AgentRegistry; from limo.config import Settings; print(len(AgentRegistry(Settings(_env_file=None).skills_dir).list()))"` → `7`

### STEP-13 API
- file: `engine/limo/api/__init__.py` (empty), `errors.py`, `projects_routes.py`, `agents_routes.py` (create)
- do:
  - `errors.py`: `install_error_handlers(app: FastAPI)`: `LimoError` → `JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})`; `RequestValidationError` → 422 with code `validation_error` and message `"<loc joined by .>: <msg>"` of the first error.
  - `projects_routes.py`: `projects_router(service: ProjectService) -> APIRouter` with prefix `/api/projects`: `POST ""` (status 201, `response_model=Project`) → `service.add(body)`; `GET ""` (`response_model=list[Project]`) → `service.list()`. Handlers are plain `def` (not `async`).
  - `agents_routes.py`: `agents_router(registry: AgentRegistry) -> APIRouter` with prefix `/api/agents`: `GET ""` → `registry.list()`.
- like: router factories take their service as an argument; no module-level instances
- verify: `cd engine && uv run python -c "import limo.api.projects_routes, limo.api.agents_routes"` → exit 0

### STEP-14 app wiring
- file: `engine/limo/app.py` (create)
```python
from dataclasses import dataclass

from fastapi import FastAPI

from limo.agents.registry import AgentRegistry
from limo.api.agents_routes import agents_router
from limo.api.errors import install_error_handlers
from limo.api.projects_routes import projects_router
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.executor.ports import Executor
from limo.projects.repo import ProjectRepo
from limo.projects.service import ProjectService
from limo.store.db import migrate


@dataclass(frozen=True)
class Deps:
    executor: Executor


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    deps = deps or Deps(executor=LocalExecutor())
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    migrate(settings.db_path)
    projects = ProjectService(
        ProjectRepo(settings.db_path), deps.executor, settings.workspaces_dir, settings.command_timeout_s
    )
    app = FastAPI(title="Limo", openapi_url="/api/openapi.json", docs_url=None, redoc_url=None)
    install_error_handlers(app)
    app.include_router(projects_router(projects))
    app.include_router(agents_router(AgentRegistry(settings.skills_dir)))
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())
```
- verify: `mise run test:engine` → 10 FT functions (13 test cases with parametrize) pass

### STEP-15 format, then quality gates
- file: `mise.toml` (edit); any file created above only if a gate still fails
- do: add this task after `[tasks.lint]`, then run `mise run fmt`, then `mise run gates`; fix only reported lines in files this plan created, then run `mise run fmt` again
```toml
[tasks.fmt]
description = "Auto-format and auto-fix (ruff)"
dir = "engine"
run = ["uv run ruff check --fix .", "uv run ruff format ."]
```
- verify: `mise run gates` → exit 0; `mise run test:engine` → 13 passed

### STEP-16 pin the engine to Python 3.12
- file: `engine/pyproject.toml` (edit)
- do: change `requires-python = ">=3.12"` to `requires-python = ">=3.12,<3.13"`; run `mise run setup`
- verify: `engine/.venv/bin/python --version` → `Python 3.12.x`

### STEP-17 test: clone of an empty repo fails cleanly (test first)
- file: `engine/tests/functional/test_projects.py` (edit), `engine/tests/builders.py` (edit)
- do: in `builders.py` add `make_empty_bare_repo(root: Path, name: str) -> str` that runs `git init --bare <root>/<name>.git` (via `_git`, cwd=root) and returns its `as_uri()`. In `test_projects.py` add `test_ft_1_11_empty_repo_clone_fails` (docstring starts `"""FT-1.11 `) per the Functional tests table.
- verify: `mise run test:engine -- -k ft_1_11` → FAIL: status 201 instead of 502

### STEP-18 check `git rev-parse`
- file: `engine/limo/projects/service.py` (edit)
- do: in `add`, move the cleanup into a private method `_fail_clone(path: Path) -> ExternalError` that runs `shutil.rmtree(path, ignore_errors=True)` and returns `ExternalError("clone_failed", "could not clone the repository")`; use it for the two existing clone failures. Wrap the rev-parse call like the clone call (`ExecutorError` → `raise self._fail_clone(path) from e`); then if `branch.code != 0` or `branch.stdout.strip()` is empty → `raise self._fail_clone(path)`.
- verify: `mise run test:engine -- -k ft_1_11` → passed

### STEP-19 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created)
- do: `mise run fmt`, then `mise run gates`, then `mise run test`
- verify: gates exit 0; `mise run test` → 14 passed

## Do not
- add UI code, SSE, auth, or any Claude API client
- write to `.git/info/exclude`, branches, or issues (later tickets)
- call `subprocess` outside `limo/executor/local.py` and `tests/`
- edit `scripts/fx.py`, `skills/`, or `context/`

## Doc updates
- context/layout.md: Tree — drop "(planned)" from `engine/`; Where to put new things — endpoint ref `engine/limo/api/projects_routes.py`, port + adapter ref `engine/limo/executor/ports.py` + `local.py`, migration ref `engine/limo/store/migrations/001_projects.sql`, functional test ref `engine/tests/functional/test_projects.py`; Wiring — `engine/limo/app.py` exists
- context/api.md: Reference implementations — endpoint: `engine/limo/api/projects_routes.py`; error handlers: `engine/limo/api/errors.py`
- context/data.md: Migrations location `engine/limo/store/migrations/` (exists); `projects` columns as in `001_projects.sql`
- context/testing.md: Harness reference test `engine/tests/functional/test_projects.py`; builders at `engine/tests/builders.py`
- context/stack.md: `mise.toml` exists with pinned python, node, uv; deps in `engine/pyproject.toml` + `engine/uv.lock`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
