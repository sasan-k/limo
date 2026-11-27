---
ticket: TKT-14
feature: limo
scenarios: [SC-46, SC-47, SC-48]
scope: [ui, api, agents]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/prompts.feature, work/limo/reqs.md#REQ-42#REQ-43, work/limo/questions.md#Q-9, DESIGN.md (Limo = standalone app), context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/data.md, context/layout.md, context/adr/ADR-10.md, work/limo/plans/TKT-12.md#Design, engine/limo/agents/registry.py, engine/limo/agents/service.py, engine/limo/vcs/git.py, engine/limo/executor/local.py, engine/limo/common/errors.py, engine/limo/api/errors.py, engine/limo/app.py, engine/tests/builders.py, engine/tests/functional/test_agents.py:25-40, ui/src/**, ui/tests/harness.tsx]
---
# TKT-14: Prompt editor saves versions and rolls back

## Design
- where: new `limo/prompts/` (models, repo, service), `api/prompts_routes.py`, `vcs/git.py` (file-level git ops), migration `015_prompt_saves.sql`, `app.py`; UI `PromptsPage`, `PromptEditor`, `PromptHistory`, `api/prompts.ts`, `putJson`; test builder `make_skills_repo`.
- responsibilities:
  - `GitOps.file_versions / commit_file / restore_file` — `git log` / `git commit -- <path>` / `git checkout <sha> -- <path>` for one file, run in the agent's skills directory (paths relative to it)
  - `PromptService` — list, read, save (optimistic `base_version` check, no commit when unchanged), history (≤ 50, newest first, UTC times), rollback (restore + commit as a new version); records each commit in `prompt_saves` and publishes `prompt.saved`
  - `PromptSaveRepo.add` — audit row per save/rollback (security.md › Audit)
  - UI: `PromptsPage` (agent + file selects), `PromptEditor` (draft, Save), `PromptHistory` (versions, Roll back)
- reuse: `GitOps._git` + executor argv (ADR-10); `AGENT_NAMES`; `NotFound`/`Conflict`; `EventBus` (`prompt.saved` already in `EVENT_TYPES`); repo pattern of `cards/repo.py`; UI `getJson`/`postJson`, `Button`, `formatTime`, Vitest `serveApi`. Prompts stay global in `settings.skills_dir` (Q-9). Searched `limo/agents`, `limo/vcs` for file-level git helpers: none.
- contracts (`{name}` ∈ AGENT_NAMES else 404 `agent_not_found`; `path` query matches `^(SKILL\.md|templates(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+)$`, ≤ 200 chars, else 422 `validation_error`; file must exist under `skills/<name>/`, not a symlink, else 404 `file_not_found`; git failure (e.g. skills not in a git repo) → 409 `git_failed`):
  - `GET /api/agents/{name}/files` → `["SKILL.md", "templates/…" sorted]`
  - `GET /api/agents/{name}/file?path=` → `PromptFile {"agent", "path", "content", "version": sha|null}` (version = last commit touching the file)
  - `PUT /api/agents/{name}/file?path=` body `{"content": str ≤ 262144 chars, "base_version"?: 40-hex}` (extra forbid) → `PromptFile`; `base_version` ≠ current version → 409 `version_conflict` (file unchanged); content equal to the file → no commit, same version; else write + commit `prompt: <name> <path>`
  - `GET /api/agents/{name}/history?path=` → `[PromptVersion {"version", "saved_at" (UTC ISO), "message"}]` newest first, ≤ 50
  - `POST /api/agents/{name}/rollback?path=` body `{"version": 40-hex}` → `PromptFile`; version not in the history → 404 `version_not_found`; version = current → no commit; restored content equal to current → no commit; else commit `prompt: rollback <name> <path> to <sha7>`
  - SSE `prompt.saved` (after each commit), `project_id` null, payload `{"agent", "path", "version"}`
- data: `015_prompt_saves.sql` → table `prompt_saves (id INTEGER PK AUTOINCREMENT, agent, path, version, action CHECK IN ('save','rollback'), created_at)`
- decisions: version = git commit sha of the app repo (REQ-43); commits touch only the one path (`git commit -- <path>`), other staged changes stay staged; optimistic concurrency via `base_version`. No new ADR, no new dependency.

## Quality
### Security
- authn: n/a: ADR-7, 127.0.0.1 only
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: agent name against AGENT_NAMES; path regex (no `..`, no leading `.` segments) + resolved path must stay inside `skills/<name>/` and not be a symlink (security.md › paths); content ≤ 256 KB (security.md › limits); sha `^[0-9a-f]{40}$`; bodies `extra="forbid"`
- injection: git via executor argv lists; path passed after `--`; sha validated before use as a revision
- data exposure / PII: prompt bodies returned only to the local UI; never logged (security.md › Data)
- secrets: none; prompts must not contain keys (unchanged)
- rate limit / abuse: n/a: local single user; body cap 256 KB
- audit: every save/rollback commit → `prompt_saves` row with time (security.md › Audit)
### Performance
- queries (N+1, indexes): one INSERT per commit; no reads
- pagination / limits: history `git log -n 50`
- payload size: file ≤ 256 KB; history ≤ 50 × ~120 B
- caching: none server-side; react-query invalidated by `prompt.saved`
- external calls (timeouts/retries): local git via executor with `command_timeout_s`
- sync vs async: sync routes (threadpool)
- NFR targets: none beyond NFR-9 (FT-14.9 event) and NFR-10 (FT-14.15 axe both modes)

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 save `PUT /api/agents/{name}/file` | FT-14.1, FT-14.2, FT-14.9 | FT-14.4 | FT-14.5 | FT-14.6 | FT-14.10 | FT-14.7 | FT-14.8 | n/a: git is local |
| OP-2 files, read, history `GET /api/agents/{name}/files`, `/file`, `/history` | FT-14.1, FT-14.2 | FT-14.4 | FT-14.5 | n/a: read only | FT-14.10 | n/a: read only | FT-14.3 | n/a: git is local |
| OP-3 rollback `POST /api/agents/{name}/rollback` | FT-14.3 | FT-14.4 | FT-14.5 | n/a: rollback always lands on top | FT-14.10 | FT-14.7 | n/a: any listed version | n/a: git is local |
| OP-4 prompts page `ui/src/pages/PromptsPage.tsx` | FT-14.11, FT-14.12, FT-14.14 | FT-14.11 | n/a: files come from the list | FT-14.13 | n/a: engine decides | n/a: Save disabled while unchanged or pending | FT-14.15 | n/a: engine errors shown as in FT-14.13 |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-14.1 | SC-46, OP-1:happy, OP-2:happy | `engine/tests/functional/test_prompts.py` | module `settings` fixture: `skills_dir=make_skills_repo(tmp_path)`, `sse_heartbeat_s=0.2`; `add_cart_project`; `f = GET /api/agents/build/file?path=SKILL.md`; `h0 = len(GET …/history?path=SKILL.md)` | `PUT /api/agents/build/file?path=SKILL.md` `{"content": f["content"] + "Always run the formatter last.\n", "base_version": f["version"]}`; then `start_and_wait(client, "build")` | PUT 200, `version != f["version"]`; history length `h0 + 1`, `[0]["version"] ==` PUT version, `[0]["message"] == "prompt: build SKILL.md"`; `"Always run the formatter last." in llm.requests[-1].system` |
| FT-14.2 | SC-47, OP-1:happy, OP-2:happy | same | `GET /api/agents/build/files` contains `"SKILL.md"` (first) and `"templates/build-report.md"`; read that file + history length | PUT it with content + `"- duration: <minutes>\n"` | history length +1; `GET …/file?path=templates/build-report.md` content contains `- duration: <minutes>` |
| FT-14.3 | SC-48, OP-3:happy, OP-2:boundary | same | save A (`content0 + "A\n"`) → `va`; save B (`content0 + "B\n"`, base `va`) → `vb` | `POST /api/agents/build/rollback?path=SKILL.md` `{"version": va}` | 200, content == A content, `version not in (va, vb)`; history `[0].version ==` new version, `[1].version == vb`, `[0].message.startswith("prompt: rollback build SKILL.md to ")`; every `saved_at` ends with `+00:00` |
| FT-14.4 | OP-1:validation, OP-2:validation, OP-3:validation | same | none | `GET …/build/file?path=` each of `../SKILL.md`, `templates/../x.md`, `notes.md`; PUT content of 262145 chars; PUT `{"content": "x", "extra": 1}`; rollback `{"version": "abc"}` | every response 422 with `body["error"]["code"] == "validation_error"` |
| FT-14.5 | OP-1:not-found, OP-2:not-found, OP-3:not-found | same | none | `GET /api/agents/deploy/file?path=SKILL.md`; `PUT /api/agents/build/file?path=templates/nope.md` `{"content": "x"}`; rollback `{"version": "0" * 40}` | 404 codes `agent_not_found`, `file_not_found`, `version_not_found` |
| FT-14.6 | OP-1:conflict | same | `v0` = current; save X with base `v0` | PUT Y with base `v0` | 409 `version_conflict`; GET content == X content |
| FT-14.7 | OP-1:idempotency, OP-3:idempotency | same | `f` = current file, `h0` history length | PUT `{"content": f["content"], "base_version": f["version"]}`; rollback `{"version": f["version"]}` | both 200 with `version == f["version"]`; history length still `h0` |
| FT-14.8 | OP-1:boundary | same | none | PUT content `"x" * 262143 + "\n"` | 200; GET content length 262144 |
| FT-14.9 | OP-1:happy | same | open `GET /api/events`, `next(lines) == ": connected"` | PUT SKILL.md with an added line | `ev = next_event(lines, "prompt.saved")`: `ev["project_id"] is None`, payload `{"agent": "build", "path": "SKILL.md", "version": <PUT version>}` |
| FT-14.10 | OP-1:invalid-state, OP-2:invalid-state, OP-3:invalid-state | same | own app: `shutil.copytree(Settings(_env_file=None).skills_dir, tmp_path / "plain" / "skills")` (no git), `Settings(data_dir=tmp_path / "data2", skills_dir=…, _env_file=None)`, `Deps(LocalExecutor(path_prefix=settings.scripts_dir), FakeLlm(), FakeHost())` | GET history; PUT `{"content": "x"}`; rollback `{"version": "a" * 40}` | each 409 `git_failed`; `SKILL.md` on disk unchanged |
| FT-14.11 | SC-46, OP-4:happy, OP-4:validation | `ui/tests/Prompts.test.tsx` | `serveApi` with agents, files, `build` SKILL.md version B, history [B, A], `PUT` → C | Save disabled; type new content; click Save | `ccccccc` appears in history; recorded PUT body `{content, base_version: B}` |
| FT-14.12 | SC-48, OP-4:happy | same | as FT-14.11, `POST …/rollback` → content `# A` | no Roll back on the newest version; click `Roll back to aaaaaaa` | editor shows `# A`; POST body `{version: A}` |
| FT-14.13 | OP-4:conflict | same | PUT → 409 `version_conflict` | edit, Save | message `SKILL.md changed since bbbbbbb` |
| FT-14.14 | SC-47, OP-4:happy | same | `templates/build-report.md` file + history routes | choose it in `File` | editor shows `# Build report` |
| FT-14.15 | OP-4:boundary | `ui/e2e/prompts.spec.ts` | e2e engine (real `skills/`, read only) | per mode: set `limo-theme`, reload, click `Prompts` | `Content` value matches `/name: factory-build/`; history region has ≥ 1 item; axe `color-contrast` violations `[]` in both modes |

## Context pack
- `engine/limo/vcs/git.py` — add file-level ops
- `engine/limo/cards/repo.py` — repo pattern to imitate
- `engine/limo/cards/service.py` — service style to imitate
- `engine/limo/common/constants.py` — AGENT_NAMES (read)
- `engine/limo/common/errors.py` — error types (read)
- `engine/limo/events/bus.py` — `EventBus.publish` (read)
- `engine/limo/api/cards_routes.py` — router to imitate
- `engine/limo/app.py` — wiring
- `engine/pyproject.toml` — import-linter source modules
- `engine/tests/builders.py` — add `make_skills_repo`; `add_cart_project`, `start_and_wait`, `next_event`
- `engine/tests/conftest.py` — fixtures (read)
- `engine/tests/functional/test_agent_cards.py` — SSE test + settings override pattern to imitate
- `ui/src/api/client.ts`, `ui/src/api/types.ts`, `ui/src/api/events.ts`, `ui/src/App.tsx` — edit
- `ui/tests/harness.tsx` — `serveApi`, `renderApp` (read)
- `ui/e2e/board.spec.ts` — e2e style to imitate

## Steps
### STEP-1 Audit table
- file: `engine/limo/store/migrations/015_prompt_saves.sql` (create)
- do:
```sql
CREATE TABLE prompt_saves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent TEXT NOT NULL,
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('save', 'rollback')),
  created_at TEXT NOT NULL
);
```
- verify: `mise run test:engine -- -k ft_1_` → passes

### STEP-2 File-level git ops
- file: `engine/limo/vcs/git.py` (edit)
- do: add `from dataclasses import dataclass`; module constant `IDENTITY = ("-c", "user.name=Limo", "-c", "user.email=limo@localhost")` and use it in `commit_and_push` (`self._git(workspace, *IDENTITY, "commit", "-m", message)`); add
```python
@dataclass(frozen=True)
class FileVersion:
    version: str
    saved_at: str
    message: str
```
  and these `GitOps` methods:
```python
    def file_versions(self, cwd: Path, path: str, limit: int) -> list[FileVersion]:
        result = self._git(cwd, "log", f"-n{limit}", "--format=%H%x09%cI%x09%s", "--", path)
        if result.code != 0:
            raise GitError(result.stderr)
        versions: list[FileVersion] = []
        for line in result.stdout.splitlines():
            sha, _, rest = line.partition("\t")
            saved_at, _, message = rest.partition("\t")
            versions.append(FileVersion(sha, saved_at, message))
        return versions

    def commit_file(self, cwd: Path, path: str, message: str) -> None:
        committed = self._git(cwd, *IDENTITY, "commit", "-m", message, "--", path)
        if committed.code != 0:
            raise GitError(committed.stderr or committed.stdout)

    def restore_file(self, cwd: Path, version: str, path: str) -> None:
        restored = self._git(cwd, "checkout", version, "--", path)
        if restored.code != 0:
            raise GitError(restored.stderr)
```
- verify: `cd engine && uv run mypy` → `Success`; `mise run test:engine -- -k "shipping or ft_7"` → pass

### STEP-3 Prompt models
- file: `engine/limo/prompts/__init__.py` (create, empty), `engine/limo/prompts/models.py` (create)
- do:
```python
from pydantic import BaseModel, ConfigDict, Field

PATH_PATTERN = r"^(SKILL\.md|templates(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+)$"
SHA_PATTERN = r"^[0-9a-f]{40}$"
MAX_CONTENT = 262_144


class PromptFile(BaseModel):
    agent: str
    path: str
    content: str
    version: str | None


class PromptVersion(BaseModel):
    version: str
    saved_at: str
    message: str


class PromptSaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=MAX_CONTENT)
    base_version: str | None = Field(default=None, pattern=SHA_PATTERN)


class RollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=SHA_PATTERN)
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-4 Audit repo
- file: `engine/limo/prompts/repo.py` (create)
- like: `engine/limo/cards/repo.py`
- do: `class PromptSaveRepo(db_path: Path)` with `add(self, agent: str, path: str, version: str, action: str) -> None` running `INSERT INTO prompt_saves (agent, path, version, action, created_at) VALUES (?, ?, ?, ?, ?)` with `datetime.now(UTC).isoformat()`; commit; close.
- verify: `cd engine && uv run mypy` → `Success`

### STEP-5 Skills repo builder
- file: `engine/tests/builders.py` (edit)
- do: add (`import shutil` at top)
```python
def make_skills_repo(root: Path) -> Path:
    """Copy the real skills/ into a new git repo <root>/app with one commit; return <root>/app/skills."""
    app = root / "app"
    shutil.copytree(Settings(_env_file=None).skills_dir, app / "skills")
    _git("init", "-b", "main", cwd=app)
    _git("add", ".", cwd=app)
    _git("-c", "user.name=limo", "-c", "user.email=limo@example.com", "commit", "-m", "init", cwd=app)
    return app / "skills"
```
- verify: `cd engine && uv run ruff check tests/builders.py` → clean

### STEP-6 Engine functional tests
- file: `engine/tests/functional/test_prompts.py` (create)
- like: `engine/tests/functional/test_agent_cards.py`
- do: FT-14.1 … FT-14.10 exactly as in the table. Module fixture overriding conftest `settings`:
```python
@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        skills_dir=make_skills_repo(tmp_path),
        anthropic_api_key="sk-canary-123",
        sse_heartbeat_s=0.2,
        _env_file=None,
    )
```
  Helpers: `FILE = "/api/agents/build/file?path=SKILL.md"`, `HISTORY = "/api/agents/build/history?path=SKILL.md"`, `ROLLBACK = "/api/agents/build/rollback?path=SKILL.md"`; `def _save(client, content, base=None) -> httpx.Response` (PUT `{"content": content}` plus `"base_version": base` when given). Names `test_ft_14_<k>_<behavior>`; docstrings start `"""FT-14.<k> …`. FT-14.10 builds its own app inside `with TestClient(create_app(plain_settings, deps)) as c:` and checks `SKILL.md` text before/after.
- verify: `mise run test:engine -- -k ft_14` → `FAIL: 404` (no routes)

### STEP-7 Prompt service
- file: `engine/limo/prompts/service.py` (create)
- like: `engine/limo/cards/service.py`
- do:
```python
from datetime import UTC, datetime
from pathlib import Path

from limo.common.constants import AGENT_NAMES
from limo.common.errors import Conflict, NotFound
from limo.events.bus import EventBus
from limo.prompts.models import PromptFile, PromptSaveIn, PromptVersion
from limo.prompts.repo import PromptSaveRepo
from limo.vcs.git import FileVersion, GitError, GitOps

HISTORY_LIMIT = 50


def _utc(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(UTC).isoformat()


class PromptService:
    """Agent prompt and reference files in skills/; every change is a git commit (REQ-42, REQ-43)."""

    def __init__(self, skills_dir: Path, git: GitOps, saves: PromptSaveRepo, events: EventBus) -> None:
        self._skills_dir = skills_dir
        self._git = git
        self._saves = saves
        self._events = events

    def files(self, agent: str) -> list[str]:
        root = self._agent_dir(agent)
        templates = root / "templates"
        if not templates.is_dir():
            return ["SKILL.md"]
        refs = sorted(p.relative_to(root).as_posix() for p in templates.rglob("*") if p.is_file())
        return ["SKILL.md", *refs]

    def read(self, agent: str, path: str) -> PromptFile:
        root, file = self._resolve(agent, path)
        return PromptFile(agent=agent, path=path, content=file.read_text(), version=self._head(root, path))

    def history(self, agent: str, path: str) -> list[PromptVersion]:
        root, _ = self._resolve(agent, path)
        return [
            PromptVersion(version=v.version, saved_at=_utc(v.saved_at), message=v.message)
            for v in self._versions(root, path, HISTORY_LIMIT)
        ]

    def save(self, agent: str, path: str, data: PromptSaveIn) -> PromptFile:
        root, file = self._resolve(agent, path)
        head = self._head(root, path)
        if data.base_version is not None and data.base_version != head:
            raise Conflict("version_conflict", f"{path} changed since {data.base_version[:7]}")
        if file.read_text() != data.content:
            file.write_text(data.content)
            self._commit(agent, root, path, (f"prompt: {agent} {path}", "save"))
        return self.read(agent, path)

    def rollback(self, agent: str, path: str, version: str) -> PromptFile:
        root, file = self._resolve(agent, path)
        known = [v.version for v in self._versions(root, path, HISTORY_LIMIT)]
        if version not in known:
            raise NotFound("version_not_found", f"version {version[:7]} is not in the history of {path}")
        before = file.read_text()
        if version != known[0]:
            try:
                self._git.restore_file(root, version, path)
            except GitError as e:
                raise Conflict("git_failed", "prompt rollback failed") from e
        if file.read_text() != before:
            self._commit(agent, root, path, (f"prompt: rollback {agent} {path} to {version[:7]}", "rollback"))
        return self.read(agent, path)

    def _commit(self, agent: str, root: Path, path: str, what: tuple[str, str]) -> None:
        message, action = what
        try:
            self._git.commit_file(root, path, message)
        except GitError as e:
            raise Conflict("git_failed", "prompt commit failed") from e
        version = self._head(root, path) or ""
        self._saves.add(agent, path, version, action)
        self._events.publish("prompt.saved", None, {"agent": agent, "path": path, "version": version})

    def _versions(self, root: Path, path: str, limit: int) -> list[FileVersion]:
        try:
            return self._git.file_versions(root, path, limit)
        except GitError as e:
            raise Conflict("git_failed", "prompt history unavailable: skills are not in a git repository") from e

    def _head(self, root: Path, path: str) -> str | None:
        versions = self._versions(root, path, 1)
        return versions[0].version if versions else None

    def _agent_dir(self, agent: str) -> Path:
        if agent not in AGENT_NAMES:
            raise NotFound("agent_not_found", f"agent {agent} not found")
        return self._skills_dir / agent

    def _resolve(self, agent: str, path: str) -> tuple[Path, Path]:
        root = self._agent_dir(agent)
        file = root / path
        inside = file.resolve().is_relative_to(root.resolve())
        if file.is_symlink() or not file.is_file() or not inside:
            raise NotFound("file_not_found", f"{path} not found for agent {agent}")
        return root, file
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-8 Prompt routes
- file: `engine/limo/api/prompts_routes.py` (create)
- like: `engine/limo/api/cards_routes.py`
- do:
```python
from typing import Annotated

from fastapi import APIRouter, Query

from limo.prompts.models import PATH_PATTERN, PromptFile, PromptSaveIn, PromptVersion, RollbackIn
from limo.prompts.service import PromptService

FilePath = Annotated[str, Query(pattern=PATH_PATTERN, max_length=200)]


def prompts_router(service: PromptService) -> APIRouter:
    router = APIRouter(prefix="/api/agents/{name}")

    @router.get("/files", response_model=list[str])
    def list_files(name: str) -> list[str]:
        return service.files(name)

    @router.get("/file", response_model=PromptFile)
    def read_file(name: str, path: FilePath) -> PromptFile:
        return service.read(name, path)

    @router.put("/file", response_model=PromptFile)
    def save_file(name: str, path: FilePath, body: PromptSaveIn) -> PromptFile:
        return service.save(name, path, body)

    @router.get("/history", response_model=list[PromptVersion])
    def file_history(name: str, path: FilePath) -> list[PromptVersion]:
        return service.history(name, path)

    @router.post("/rollback", response_model=PromptFile)
    def rollback_file(name: str, path: FilePath, body: RollbackIn) -> PromptFile:
        return service.rollback(name, path, body.version)

    return router
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-9 Wiring
- file: `engine/limo/app.py` (edit), `engine/pyproject.toml` (edit)
- do: import `prompts_router`, `PromptService`, `PromptSaveRepo`; after the board router add `app.include_router(prompts_router(PromptService(settings.skills_dir, git, PromptSaveRepo(settings.db_path), events)))` (`git` is the existing `GitOps` variable, `events` the existing `EventBus`). In `pyproject.toml` add `"limo.prompts"` to `source_modules` of the ADR-4 contract.
- verify: `mise run test:engine -- -k ft_14` → 10 passed; `mise run arch` → kept

### STEP-10 Regenerate API types
- file: `ui/src/api/schema.d.ts` (generated)
- do: `mise run gen:api`
- verify: `grep -c "PromptVersion" ui/src/api/schema.d.ts` → ≥ 1

### STEP-11 Prompt component tests
- file: `ui/tests/Prompts.test.tsx` (create)
- do: exact contents:
```tsx
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { PromptFile, PromptVersion } from "@/api/types";

import { renderApp, serveApi } from "./harness";

const A = "a".repeat(40);
const B = "b".repeat(40);
const C = "c".repeat(40);
const FILE = "/api/agents/build/file?path=SKILL.md";
const HISTORY = "/api/agents/build/history?path=SKILL.md";

function file(content: string, version: string, path = "SKILL.md"): PromptFile {
  return { agent: "build", path, content, version };
}

function version(v: string, message: string): PromptVersion {
  return { version: v, saved_at: "2026-11-26T14:05:00+00:00", message };
}

function routes(): { current: Record<string, unknown> } {
  return {
    current: {
      "/api/agents": [{ name: "plan" }, { name: "build" }],
      "/api/agents/build/files": ["SKILL.md", "templates/build-report.md"],
      [FILE]: file("# Build\n", B),
      [HISTORY]: [version(B, "prompt: build SKILL.md"), version(A, "init")],
    },
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

async function openPrompts(): Promise<void> {
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: "Prompts" }));
  await screen.findByDisplayValue("# Build");
}

test("FT-14.11 saving the edited prompt sends content and base version, then shows the new version", async () => {
  const api = routes();
  api.current[`PUT ${FILE}`] = { status: 200, body: file("# Build\nAlways run the formatter last.\n", C) };
  const calls = serveApi(api);
  await openPrompts();
  const save = screen.getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  const text = "# Build\nAlways run the formatter last.\n";
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: text } });
  api.current[FILE] = file(text, C);
  api.current[HISTORY] = [version(C, "prompt: build SKILL.md"), version(B, "prompt: build SKILL.md")];
  fireEvent.click(save);
  expect(await screen.findByText("ccccccc")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")).toEqual({
    method: "PUT",
    path: FILE,
    body: { content: text, base_version: B },
  });
});

test("FT-14.12 rolling back posts the chosen version and shows the restored content", async () => {
  const api = routes();
  api.current[`POST /api/agents/build/rollback?path=SKILL.md`] = { status: 200, body: file("# A\n", C) };
  const calls = serveApi(api);
  await openPrompts();
  await screen.findByRole("button", { name: "Roll back to aaaaaaa" });
  expect(screen.queryByRole("button", { name: "Roll back to bbbbbbb" })).toBeNull();
  api.current[FILE] = file("# A\n", C);
  fireEvent.click(screen.getByRole("button", { name: "Roll back to aaaaaaa" }));
  expect(await screen.findByDisplayValue("# A")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ version: A });
});

test("FT-14.13 a stale save shows the engine's conflict message", async () => {
  const api = routes();
  const conflict = { error: { code: "version_conflict", message: "SKILL.md changed since bbbbbbb" } };
  api.current[`PUT ${FILE}`] = { status: 409, body: conflict };
  serveApi(api);
  await openPrompts();
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: "# Mine\n" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("SKILL.md changed since bbbbbbb")).toBeInTheDocument();
});

test("FT-14.14 choosing a reference file loads that file", async () => {
  const api = routes();
  const ref = "/api/agents/build/file?path=templates%2Fbuild-report.md";
  api.current[ref] = file("# Build report\n", A, "templates/build-report.md");
  api.current["/api/agents/build/history?path=templates%2Fbuild-report.md"] = [version(A, "init")];
  serveApi(api);
  await openPrompts();
  fireEvent.change(screen.getByLabelText("File"), { target: { value: "templates/build-report.md" } });
  expect(await screen.findByDisplayValue("# Build report")).toBeInTheDocument();
});
```
- verify: `mise run test:ui -- -t "FT-14"` → `FAIL: no button named "Prompts"`

### STEP-12 API client, types, events, prompt paths
- file: `ui/src/api/client.ts`, `ui/src/api/types.ts`, `ui/src/api/events.ts` (edit — replace whole file), `ui/src/api/prompts.ts` (create)
- do: `ui/src/api/client.ts`:
```ts
/** Engine error envelope message (api.md › Errors), else the HTTP status. */
async function failure(method: string, path: string, response: Response): Promise<Error> {
  const body = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
  return new Error(body?.error?.message ?? `${method} ${path} failed: ${response.status}`);
}

/** GET a JSON resource from the engine; throws on a non-2xx status. */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw await failure("GET", path, response);
  return (await response.json()) as T;
}

/** Send a JSON body to the engine; throws with the engine's error message on a non-2xx status. */
async function sendJson<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await failure(method, path, response);
  return (await response.json()) as T;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

export function putJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("PUT", path, body);
}
```
  `ui/src/api/types.ts`:
```ts
import type { components } from "./schema";

export type Agent = components["schemas"]["Agent"];
export type AgentCard = components["schemas"]["AgentCard"];
export type LastRun = components["schemas"]["LastRun"];
export type Board = components["schemas"]["Board"];
export type BoardTicket = components["schemas"]["BoardTicket"];
export type InboxItem = components["schemas"]["InboxItem"];
export type Project = components["schemas"]["Project"];
export type PromptFile = components["schemas"]["PromptFile"];
export type PromptVersion = components["schemas"]["PromptVersion"];
```
  `ui/src/api/events.ts`:
```ts
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

/** SSE event type → REST queries it invalidates (api.md › SSE events; REST stays the truth). */
export const INVALIDATES: Record<string, QueryKey[]> = {
  "run.started": [["agent-cards"]],
  "run.updated": [["agent-cards"]],
  "run.finished": [["agent-cards"], ["board"], ["inbox"]],
  "incident.opened": [["agent-cards"], ["board"], ["inbox"]],
  "cost.updated": [["agent-cards"]],
  "ticket.changed": [["board"]],
  "prompt.saved": [["prompt"], ["prompt-history"]],
};

/** Opens one EventSource on /api/events and refetches the matching queries on each event. */
export function useLiveEvents(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/events");
    for (const [type, keys] of Object.entries(INVALIDATES)) {
      source.addEventListener(type, () => {
        for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
      });
    }
    return () => source.close();
  }, [queryClient]);
}
```
  `ui/src/api/prompts.ts`:
```ts
/** `/api/agents/<agent>/<kind>?path=<path>` with the path encoded. */
export function fileUrl(agent: string, path: string, kind: "file" | "history" | "rollback" = "file"): string {
  return `/api/agents/${encodeURIComponent(agent)}/${kind}?path=${encodeURIComponent(path)}`;
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-13 Editor, history, page, nav
- file: `ui/src/components/PromptEditor.tsx`, `ui/src/components/PromptHistory.tsx`, `ui/src/pages/PromptsPage.tsx` (create), `ui/src/App.tsx` (edit)
- do: `ui/src/components/PromptEditor.tsx`:
```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { putJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { PromptFile } from "@/api/types";
import { Button } from "@/components/ui/button";

/** Draft of one prompt or reference file; Save commits it as a new version (REQ-42, REQ-43). */
export function PromptEditor({ file }: { file: PromptFile }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(file.content);
  const save = useMutation({
    mutationFn: () =>
      putJson<PromptFile>(fileUrl(file.agent, file.path), { content: draft, base_version: file.version }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prompt"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt-history"] });
    },
  });
  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-sm">
        Content
        <textarea
          className="min-h-96 rounded-md border border-border bg-background p-2 font-mono text-sm"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
      </label>
      <div className="flex items-center gap-3">
        <Button size="sm" disabled={save.isPending || draft === file.content} onClick={() => save.mutate()}>
          Save
        </Button>
        {save.isError && <span className="text-destructive text-sm">{save.error.message}</span>}
      </div>
    </div>
  );
}
```
  `ui/src/components/PromptHistory.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { PromptFile, PromptVersion } from "@/api/types";
import { Button } from "@/components/ui/button";
import { formatTime } from "@/lib/format";

function VersionItem(props: { v: PromptVersion; current: boolean; busy: boolean; onRollback: () => void }) {
  const short = props.v.version.slice(0, 7);
  return (
    <li className="flex flex-col gap-1">
      <span className="font-mono">{short}</span>
      <span className="text-muted-foreground">
        {formatTime(props.v.saved_at)} · {props.v.message}
      </span>
      {!props.current && (
        <Button variant="outline" size="sm" disabled={props.busy} onClick={props.onRollback}>
          Roll back to {short}
        </Button>
      )}
    </li>
  );
}

/** Versions of one file, newest first; Roll back restores one as a new version (REQ-43). */
export function PromptHistory({ agent, path }: { agent: string; path: string }) {
  const queryClient = useQueryClient();
  const history = useQuery({
    queryKey: ["prompt-history", agent, path],
    queryFn: () => getJson<PromptVersion[]>(fileUrl(agent, path, "history")),
  });
  const rollback = useMutation({
    mutationFn: (version: string) => postJson<PromptFile>(fileUrl(agent, path, "rollback"), { version }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["prompt"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt-history"] });
    },
  });
  if (history.isPending) return <p className="text-muted-foreground text-sm">Loading history…</p>;
  if (history.isError) return <p className="text-destructive text-sm">{history.error.message}</p>;
  return (
    <section aria-label="history" className="flex flex-col gap-2 text-sm">
      <h2 className="font-semibold">History</h2>
      {rollback.isError && <p className="text-destructive">{rollback.error.message}</p>}
      <ol className="flex flex-col gap-2">
        {history.data.map((v, i) => (
          <VersionItem
            key={v.version}
            v={v}
            current={i === 0}
            busy={rollback.isPending}
            onRollback={() => rollback.mutate(v.version)}
          />
        ))}
      </ol>
    </section>
  );
}
```
  `ui/src/pages/PromptsPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import { fileUrl } from "@/api/prompts";
import type { Agent, PromptFile } from "@/api/types";
import { PromptEditor } from "@/components/PromptEditor";
import { PromptHistory } from "@/components/PromptHistory";

function Select(props: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      {props.label}
      <select
        className="rounded-md border border-border bg-background px-2 py-1"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      >
        {props.options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

/** View and edit each agent's prompt and reference files, with versions (REQ-42, REQ-43). */
export function PromptsPage() {
  const [agent, setAgent] = useState("build");
  const [path, setPath] = useState("SKILL.md");
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => getJson<Agent[]>("/api/agents") });
  const files = useQuery({
    queryKey: ["prompt-files", agent],
    queryFn: () => getJson<string[]>(`/api/agents/${encodeURIComponent(agent)}/files`),
  });
  const file = useQuery({
    queryKey: ["prompt", agent, path],
    queryFn: () => getJson<PromptFile>(fileUrl(agent, path)),
  });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4">
        <Select
          label="Agent"
          value={agent}
          options={agents.data?.map((a) => a.name) ?? [agent]}
          onChange={(v) => {
            setAgent(v);
            setPath("SKILL.md");
          }}
        />
        <Select label="File" value={path} options={files.data ?? [path]} onChange={setPath} />
      </div>
      {file.isError && <p className="text-destructive">{file.error.message}</p>}
      {file.data && (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <PromptEditor key={`${agent}/${path}/${file.data.version}`} file={file.data} />
          <PromptHistory agent={agent} path={path} />
        </div>
      )}
    </div>
  );
}
```
  `ui/src/App.tsx`: add `import { PromptsPage } from "@/pages/PromptsPage";` after the InboxPage import and change `PAGES` to `{ Agents: AgentsPage, Board: BoardPage, Inbox: InboxPage, Prompts: PromptsPage }`
- verify: `mise run test:ui` → 14 passed

### STEP-14 E2E prompts page
- file: `ui/e2e/prompts.spec.ts` (create)
- like: `ui/e2e/board.spec.ts`
- do:
```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-14.15 prompts page shows build's prompt and history in light and dark with AA contrast", async ({
  page,
}) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Prompts" }).click();
    await expect(page.getByLabel("Content")).toHaveValue(/name: factory-build/);
    await expect(page.getByRole("region", { name: "history" }).locator("li").first()).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
```
- verify: `mise run test:e2e` → 4 passed

### STEP-15 Format and full gates
- file: none (format only)
- do: `mise run fmt`
- verify: `mise run gates` → all pass; `mise run test` → all suites pass; `git status --short skills/` → empty (tests never touch the real skills)

## Do not
- write to the real `skills/` from tests or e2e (tests use `make_skills_repo`; e2e only reads)
- `git add -A`, `git commit -a`, or commit any path other than the one file
- log prompt bodies; add packages; hard-code colors

## Doc updates
- context/api.md: Reference implementations — add `- prompts: engine/limo/api/prompts_routes.py (GET /api/agents/{name}/files; GET|PUT …/file?path=; GET …/history?path=; POST …/rollback?path=; 409 version_conflict|git_failed; event prompt.saved)`; SSE "published now" list gains `prompt.saved`
- context/data.md: add `- prompt_saves — agent, path, version (git sha), action (save|rollback), created_at — 015_prompt_saves.sql (audit)`; Stores line "git: agent prompts in skills/ (versioned by commits from the prompt editor)" stays
- context/layout.md: engine modules list gains `prompts`
- context/INDEX.md: Shape — add `- engine/limo/prompts — prompt editor: read/save/history/rollback of skills/<agent>/ files as git commits → vcs, store`
- context/testing.md: builders gain `make_skills_repo(root)` (git copy of skills/ for prompt tests); e2e reads the real skills/ (never saves)
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
