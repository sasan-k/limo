---
ticket: TKT-2
feature: limo
scenarios: [SC-3, SC-4, SC-5, SC-6, SC-7]
scope: [agents]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/agents.feature, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/layout.md, context/api.md, context/data.md, context/adr/INDEX.md, ADR-4:L2, ADR-5:L2, ADR-6:L2, ADR-9:L2, ADR-10:L2, engine/pyproject.toml, engine/limo/app.py, engine/limo/config.py, engine/limo/agents/*.py, engine/limo/projects/repo.py, engine/limo/projects/service.py, engine/tests/conftest.py, engine/tests/builders.py, engine/tests/functional/test_agents.py, skills/build/SKILL.md, claude-api skill (python streaming, fallbacks)]
---
# TKT-2: Agent runs get only their prompt, task and allowlisted tools

## Design
- where: new `limo/llm/` (port + Anthropic adapter); `limo/agents/` gains runs (models, repo, service), tools, allowlists, context pack parser; new `api/runs_routes.py`; migration `002_runs.sql`
- responsibilities:
  - `limo.llm.ports` — `LlmClient` Protocol, `LlmRequest`, `LlmResponse`, `LlmUsage`, `LlmError`
  - `limo.llm.anthropic_client.AnthropicLlm` — Messages API call (streaming, adaptive thinking, server-side fallbacks); client built lazily on first call
  - `limo.agents.allowlists` — `ALLOWLISTS: dict[str, tuple[str, ...]]` per agent
  - `limo.agents.context_pack.parse_context_pack(plan_text)` — `{path: (start, end) | None}` from a plan's `## Context pack`
  - `limo.agents.tools` — `TOOL_SPECS` (JSON schemas) and `ToolBox.call(ctx, name, input) -> ToolOutcome`; enforces allowlist, workspace confinement, Build's context pack
  - `limo.agents.repo.RunRepo` — SQL for `runs` and `tool_calls`
  - `limo.agents.service.RunService` — start a run (queued → background worker), build the request from prompt + task + tools only, run the tool loop, record outcome
  - `limo.api.runs_routes` — HTTP ↔ RunService
- reuse: `Executor` port for `run_command` (`limo/executor/ports.py`); `connect` (`limo/store/db.py`); repo pattern from `limo/projects/repo.py`; errors from `limo/common/errors.py`; `AGENT_NAMES` (`limo/common/constants.py`)
- contracts:
  - `POST /api/projects/{name}/runs` body `{"agent": one of AGENT_NAMES, "feature": ^[a-z0-9][a-z0-9-]{0,39}$, "ticket": ^TKT-\d+$ | null}` → 202 `Run` (status `queued`) · 404 `project_not_found` · 422 `validation_error`
  - `GET /api/runs/{id}` → 200 `Run` · 404 `run_not_found`
  - `GET /api/runs/{id}/tool-calls` → 200 `[ToolCall]` ordered by `seq` · 404 `run_not_found`
  - `Run` = `{id, project, agent, feature, ticket, status: queued|running|succeeded|failed, model, output: str|null, error: str|null, created_at, finished_at: str|null}`
  - `ToolCall` = `{seq: int, name: str, target: str, status: ok|error|rejected, summary: str}`
  - task text sent as the first user message: `feature=<feature> ticket=<ticket>` (or `feature=<feature>` when ticket is null)
  - tool result block: `{"type": "tool_result", "tool_use_id": id, "content": text, "is_error": bool}`
  - allowlists (exact order = order offered to the model):
    - architecture, spec, plan, close: `read_file, list_files, grep, read_ref, write_file, run_command`
    - build: `read_file, read_ref, write_file, run_command`
    - verify: `read_file, list_files, grep, read_ref, run_command`
    - resolver: `read_file, list_files, grep, host_query`
  - error texts: `tool not allowed: <name>` · `not in context pack: <path>` · `path outside workspace: <path>` · `file not found: <path>` · `invalid input: <reason>` · `host_query is not available yet` · `command failed (exit <n>): <stderr first 2000 chars>`
- data: `002_runs.sql` adds `runs` and `tool_calls` (columns in STEP-5)
- decisions: follows ADR-4 (LLM port), ADR-6 (isolated context, enforced allowlist), ADR-9 (key as SecretStr, never in requests), ADR-10 (commands via executor) · no new ADR

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): per-agent allowlist enforced in `ToolBox.call` before any handler runs (SC-4); Build reads limited to plan + `context/INDEX.md` + context pack (SC-5, SC-6)
- input validation: HTTP bodies via pydantic `extra="forbid"`; tool inputs checked per tool (required keys, types) → `invalid input`
- injection: `run_command` takes an argv list (no shell) via Executor; SQL parameterized in `agents/repo.py`; `grep` uses Python `re` (no subprocess)
- data exposure / PII: tool outputs truncated (20,000 chars); no secrets ever placed in a request (ADR-9)
- secrets: `ANTHROPIC_API_KEY` read into `SecretStr`, passed only to `AnthropicLlm`; never stored or logged
- rate limit / abuse: `max_turns` (default 50) per run; exceeded → run `failed` with `max turns reached`
- audit: every tool call recorded in `tool_calls` (name, target, status, summary)
### Performance
- queries (N+1, indexes): tool calls read in one query; index `tool_calls(run_id, seq)`, `runs(project_id, agent)`
- pagination / limits: tool-call list bounded by `max_turns` × tools per turn; no pagination needed yet
- payload size: tool output ≤ 20,000 chars; `list_files` ≤ 200 entries; `grep` ≤ 100 matches; `write_file` content ≤ 1,000,000 chars
- caching: n/a: none
- external calls (timeouts/retries): Anthropic SDK default timeout + retries (no extra loop); commands use `settings.command_timeout_s`
- sync vs async: runs execute in a single-thread `ThreadPoolExecutor` worker, never inside the HTTP request (performance.md › Async)
- NFR targets: NFR-3 (no secret in requests) → FT-2.1 asserts the request has no key; NFR-4 → all runs go through `LlmClient`

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 start run `POST /api/projects/{name}/runs` | FT-2.1 | FT-2.6 | FT-2.7 | n/a: each start is a new queued run; one-at-a-time is TKT-5 | n/a: no run states gate starting until the runner (TKT-5) | n/a: each POST creates a run by design | FT-2.14 | FT-2.9 |
| OP-2 get run `GET /api/runs/{id}` | FT-2.1 | n/a: id is an opaque string | FT-2.8 | n/a: read only | n/a: read only | n/a: read only | n/a: single item | n/a: no external call |
| OP-3 list tool calls `GET /api/runs/{id}/tool-calls` | FT-2.2 | n/a: id is an opaque string | FT-2.8 | n/a: read only | n/a: read only | n/a: read only | n/a: bounded by max_turns | n/a: no external call |
| OP-4 agent tool call `ToolBox.call` | FT-2.3 | FT-2.12 | FT-2.11 | n/a: tools do not create unique resources | FT-2.2 | n/a: reads are pure; write_file overwrites | FT-2.10 | FT-2.13 |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-2.1 | SC-3, OP-1:happy, OP-2:happy | `engine/tests/functional/test_runs.py` | cart project added (builder repo with `CLAUDE.md` = "secret house rules"); settings `anthropic_api_key="sk-canary-123"` | POST run agent `plan`, feature `cart`, ticket `TKT-1`; wait | run `succeeded`; fake LLM's 1st request: `system` == content of `skills/plan/SKILL.md`; `messages[0]` == `{"role": "user", "content": "feature=cart ticket=TKT-1"}`; tool names == plan allowlist; `json.dumps(request)` contains neither "secret house rules" nor "sk-canary-123" |
| FT-2.2 | SC-4, OP-4:invalid-state, OP-3:happy | `engine/tests/functional/test_tools.py` | cart project; fake LLM scripted: verify calls `write_file` | POST run `verify`; wait | 2nd request's last message holds tool_result `is_error: true`, content `tool not allowed: write_file`; GET tool-calls → `[{seq: 1, name: "write_file", status: "rejected", …}]` |
| FT-2.3 | SC-5, OP-4:happy | `engine/tests/functional/test_tools.py` | cart project; build calls `read_file` `src/cart.py` | POST run `build`; wait | tool_result content == content of `src/cart.py`, `is_error: false` |
| FT-2.4 | SC-6 | `engine/tests/functional/test_tools.py` | cart project; build calls `read_file` `src/payment.py` | POST run `build`; wait | tool_result `is_error: true`, content `not in context pack: src/payment.py`; tool call `status` "rejected" |
| FT-2.5 | SC-7 | `engine/tests/functional/test_runs.py` | cart project | POST run `resolver`; wait | 1st request tool names == `["read_file", "list_files", "grep", "host_query"]` |
| FT-2.6 | OP-1:validation | `engine/tests/functional/test_runs.py` | cart project | POST agent `deploy`; POST ticket `T1`; POST extra field `"model": "x"` | 422 `validation_error` each |
| FT-2.7 | OP-1:not-found | `engine/tests/functional/test_runs.py` | — | POST run on project `nope` | 404 `project_not_found` |
| FT-2.8 | OP-2:not-found, OP-3:not-found | `engine/tests/functional/test_runs.py` | — | GET `/api/runs/missing`, GET `/api/runs/missing/tool-calls` | 404 `run_not_found` each |
| FT-2.9 | OP-1:external-failure | `engine/tests/functional/test_runs.py` | cart project; fake LLM raises `LlmError("overloaded")` | POST run `plan`; wait | run `failed`, `error` starts with `llm_error:` |
| FT-2.10 | OP-4:boundary | `engine/tests/functional/test_tools.py` | cart project; plan calls `read_file` `../outside.txt` | POST run `plan`; wait | tool_result `is_error: true`, content `path outside workspace: ../outside.txt` |
| FT-2.11 | OP-4:not-found | `engine/tests/functional/test_tools.py` | cart project; plan calls `read_file` `src/nope.py` | POST run `plan`; wait | tool_result `is_error: true`, content `file not found: src/nope.py`; tool call `status` "error" |
| FT-2.12 | OP-4:validation | `engine/tests/functional/test_tools.py` | cart project; plan calls `read_file` with `{}` | POST run `plan`; wait | tool_result `is_error: true`, content starts `invalid input:` |
| FT-2.13 | OP-4:external-failure | `engine/tests/functional/test_tools.py` | cart project; build calls `run_command` `["false"]` | POST run `build`; wait | tool_result `is_error: true`, content starts `command failed (exit 1)` |
| FT-2.14 | OP-1:boundary | `engine/tests/functional/test_runs.py` | cart project; settings `max_turns=3`; fake LLM always asks `list_files` `.` | POST run `plan`; wait | run `failed`, `error` == `max turns reached`; fake LLM got exactly 3 requests |

## Context pack
- `engine/pyproject.toml` — STEP-1, STEP-13 edit
- `engine/limo/config.py` — STEP-6 edit
- `engine/limo/app.py` — STEP-12 edit
- `engine/limo/agents/models.py` — STEP-10 edit
- `engine/limo/common/constants.py` — read (AGENT_NAMES)
- `engine/limo/common/errors.py` — read (error classes)
- `engine/limo/executor/ports.py` — read (Executor, CommandResult, ExecutorError)
- `engine/limo/store/db.py` — read (`connect`)
- `engine/limo/projects/repo.py` — like: repository pattern (connection per method)
- `engine/limo/projects/service.py`:1-20 — like: constructor injection
- `engine/limo/api/projects_routes.py` — like: router factory
- `engine/tests/conftest.py` — STEP-3 edit
- `engine/tests/builders.py` — STEP-3 edit
- `skills/plan/SKILL.md` — read by FT-2.1 at test time only (do not edit)

## Steps
### STEP-1 add the Anthropic SDK
- file: `engine/pyproject.toml` (edit)
- do: add `"anthropic"` to `dependencies`; run `mise run setup`
- verify: `cd engine && uv run python -c "import anthropic"` → exit 0

### STEP-2 fake LLM
- file: `engine/tests/fakes/__init__.py` (create, empty), `engine/tests/fakes/llm.py` (create)
```python
from collections.abc import Callable

from limo.llm.ports import LlmError, LlmRequest, LlmResponse, LlmUsage


def tool_use(name: str, tool_input: dict[str, object], tool_id: str = "tu_1") -> LlmResponse:
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
    return LlmResponse(content=[block], stop_reason="tool_use", model="fake", usage=LlmUsage())


def final(text: str = "done") -> LlmResponse:
    return LlmResponse(content=[{"type": "text", "text": text}], stop_reason="end_turn", model="fake", usage=LlmUsage())


class FakeLlm:
    """Scripted Claude API: returns queued responses in order, then `final()`; records every request."""

    def __init__(self) -> None:
        self.script: list[LlmResponse] = []
        self.requests: list[LlmRequest] = []
        self.fail_with: LlmError | None = None
        self.repeat: Callable[[], LlmResponse] | None = None

    def create(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.repeat is not None:
            return self.repeat()
        return self.script.pop(0) if self.script else final()
```
- verify: none until STEP-7 (`limo.llm` does not exist yet)

### STEP-3 test fixtures and cart builder
- file: `engine/tests/conftest.py` (edit), `engine/tests/builders.py` (edit)
- do:
  - conftest: add fixture `llm() -> FakeLlm`; change `client` to take `llm` and build `create_app(settings, Deps(executor=LocalExecutor(), llm=llm))`; change `settings` to `Settings(data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", _env_file=None)`.
  - builders: add imports `time`, `from typing import Any`, `from fastapi.testclient import TestClient`; add constant `CART_PLAN` (a plan whose `## Context pack` section is exactly one line ``- `src/cart.py` — cart logic`` followed by `## Steps`), and:
```python
def add_cart_project(client: TestClient, root: Path) -> None:
    """Add project "shop" whose repo has src/cart.py, src/payment.py, CLAUDE.md and the TKT-1 plan of feature cart."""
    url = make_git_repo(
        root,
        "shop",
        {
            "src/cart.py": "def total() -> int:\n    return 0\n",
            "src/payment.py": "SECRET = 1\n",
            "CLAUDE.md": "secret house rules\n",
            "work/cart/plans/TKT-1.md": CART_PLAN,
        },
    )
    r = client.post("/api/projects", json={"name": "shop", "git_url": url, "host": "github"})
    assert r.status_code == 201


def start_and_wait(client: TestClient, agent: str, ticket: str | None = "TKT-1") -> dict[str, Any]:
    """POST a run for feature cart and poll GET /api/runs/{id} until it is succeeded or failed (5 s max)."""
    r = client.post("/api/projects/shop/runs", json={"agent": agent, "feature": "cart", "ticket": ticket})
    assert r.status_code == 202
    run_id = r.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")
```
- verify: none until STEP-12

### STEP-4 tests (test first)
- file: `engine/tests/functional/test_runs.py`, `engine/tests/functional/test_tools.py` (create)
- do: one function per FT in the Functional tests table, in the file it names. Name `test_ft_2_<k>_<behavior>`, docstring starts `"""FT-2.<k> `. Script the fake with `llm.script = [tool_use(...)]` before starting the run. The tool_result of the first tool call is `llm.requests[1].messages[-1]["content"][0]`. FT-2.14: own `TestClient(create_app(Settings(data_dir=tmp_path / "data", max_turns=3, _env_file=None), Deps(LocalExecutor(), llm)))` and `llm.repeat = lambda: tool_use("list_files", {"path": "."})`. FT-2.9: `llm.fail_with = LlmError("overloaded")`. FT-2.1 reads the expected system prompt from `Settings(_env_file=None).skills_dir / "plan" / "SKILL.md"`.
- verify: `mise run test:engine -- -k ft_2` → FAIL: `ModuleNotFoundError: No module named 'limo.llm'`

### STEP-5 runs tables
- file: `engine/limo/store/migrations/002_runs.sql` (create)
```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  agent TEXT NOT NULL,
  feature TEXT NOT NULL,
  ticket TEXT,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  model TEXT NOT NULL,
  output TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE INDEX runs_project_agent ON runs (project_id, agent);

CREATE TABLE tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id),
  seq INTEGER NOT NULL,
  name TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok', 'error', 'rejected')),
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX tool_calls_run_seq ON tool_calls (run_id, seq);
```
- verify: `cd engine && uv run python -c "import tempfile,pathlib; from limo.store.db import migrate; migrate(pathlib.Path(tempfile.mkdtemp())/'s.db')"` → exit 0

### STEP-6 settings
- file: `engine/limo/config.py` (edit)
- do: add fields `anthropic_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"))`, `default_model: str = "claude-opus-5-5"`, `max_turns: int = 50` (imports: `AliasChoices, Field, SecretStr` from pydantic)
- verify: `cd engine && uv run python -c "from limo.config import Settings; s=Settings(anthropic_api_key='x', _env_file=None); print(s.anthropic_api_key)"` → `**********`

### STEP-7 LLM port and Anthropic adapter
- file: `engine/limo/llm/__init__.py` (empty), `engine/limo/llm/ports.py`, `engine/limo/llm/anthropic_client.py` (create)
```python
# ports.py
from dataclasses import dataclass, field
from typing import Any, Protocol


class LlmError(Exception):
    pass


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class LlmRequest:
    model: str
    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]


@dataclass(frozen=True)
class LlmResponse:
    content: list[dict[str, Any]]
    stop_reason: str
    model: str
    usage: LlmUsage = field(default_factory=LlmUsage)


class LlmClient(Protocol):
    def create(self, request: LlmRequest) -> LlmResponse: ...
```
```python
# anthropic_client.py
from typing import Any

import anthropic
from pydantic import SecretStr

from limo.llm.ports import LlmError, LlmRequest, LlmResponse, LlmUsage

MAX_TOKENS = 64000


class AnthropicLlm:
    """Claude Messages API adapter. The SDK client is created on first use."""

    def __init__(self, api_key: SecretStr | None) -> None:
        self._api_key = api_key
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            key = self._api_key.get_secret_value() if self._api_key else None
            self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return self._client

    def create(self, request: LlmRequest) -> LlmResponse:
        try:
            with self._get_client().beta.messages.stream(
                model=request.model,
                max_tokens=MAX_TOKENS,
                system=request.system,
                messages=request.messages,  # type: ignore[arg-type]
                tools=request.tools,  # type: ignore[arg-type]
                thinking={"type": "adaptive"},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default", "output_config": {"effort": "high"}},
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AnthropicError as e:
            raise LlmError(str(e)) from e
        usage = message.usage
        content: list[dict[str, Any]] = [b.model_dump(mode="json", exclude_none=True) for b in message.content]
        return LlmResponse(
            content=content,
            stop_reason=str(message.stop_reason),
            model=message.model,
            usage=LlmUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
            ),
        )
```
- verify: `cd engine && uv run python -c "from limo.llm.anthropic_client import AnthropicLlm; AnthropicLlm(None)"` → exit 0

### STEP-8 allowlists and context pack parser
- file: `engine/limo/agents/allowlists.py`, `engine/limo/agents/context_pack.py` (create)
- do:
  - `allowlists.py`: `WRITE_AGENT = ("read_file", "list_files", "grep", "read_ref", "write_file", "run_command")`; `ALLOWLISTS: dict[str, tuple[str, ...]]` = architecture/spec/plan/close → `WRITE_AGENT`; build → `("read_file", "read_ref", "write_file", "run_command")`; verify → `("read_file", "list_files", "grep", "read_ref", "run_command")`; resolver → `("read_file", "list_files", "grep", "host_query")`.
  - `context_pack.py`: `parse_context_pack(plan_text: str) -> dict[str, tuple[int, int] | None]`: take lines after the line `## Context pack` up to the next line starting `## `; for each match of ``^- `([^`]+)`(?::(\d+)-(\d+))?`` map path → `(int(start), int(end))` or `None`. Strip a trailing `:a-b` inside the backticks the same way (``- `path:1-20` `` form).
- verify: `cd engine && uv run python -c "from limo.agents.context_pack import parse_context_pack as p; from pathlib import Path; print(p(Path('../work/limo/plans/TKT-1.md').read_text())['.gitignore'])"` → `None`

### STEP-9 tools
- file: `engine/limo/agents/tools.py` (create)
- do:
  - `TOOL_SPECS: dict[str, dict[str, Any]]` — one Messages API tool definition per name (`name`, `description` one line, `input_schema` JSON schema with `required`):
    `read_file {path: str, start_line?: int, end_line?: int}` · `list_files {path: str}` · `grep {pattern: str, path?: str}` · `read_ref {path: str}` (relative to the agent's skills dir, e.g. `templates/plan.md`) · `write_file {path: str, content: str}` · `run_command {argv: [str]}` · `host_query {query: str}`
  - `@dataclass(frozen=True) ToolContext`: `agent: str`, `workspace: Path`, `agent_dir: Path` (`skills/<agent>`), `readable: dict[str, tuple[int, int] | None] | None` (None = any file in workspace)
  - `@dataclass(frozen=True) ToolOutcome`: `text: str`, `status: Literal["ok", "error", "rejected"]`, `target: str`
  - `class ToolBox(executor: Executor, timeout_s: float)` with `specs(agent) -> list[dict]` (TOOL_SPECS in ALLOWLISTS order) and `call(ctx, name, tool_input) -> ToolOutcome`:
    1. `name not in ALLOWLISTS[ctx.agent]` → `rejected`, `tool not allowed: <name>`
    2. dispatch via a dict `{name: handler}`; each handler validates its input (missing/wrong-typed key → `error`, `invalid input: <key> required`)
    3. path rule (`_resolve(ctx.workspace, rel)`): `(workspace / rel).resolve()` must be inside `workspace.resolve()` else `rejected`, `path outside workspace: <rel>`
    4. `read_file`: when `ctx.readable` is not None and `rel` not in it → `rejected`, `not in context pack: <rel>`; missing → `error`, `file not found: <rel>`; a pack range `(a, b)` (or `start_line`/`end_line`) returns only lines a..b (1-based, inclusive)
    5. `list_files`: sorted names in the dir, dirs suffixed `/`, max 200; `grep`: Python `re` over files under `path` (default `.`), skip `.git/`, lines `<rel>:<n>: <line>`, max 100
    6. `read_ref`: resolve under `ctx.agent_dir` with the same confinement rule (message `path outside agent dir: <rel>`)
    7. `write_file`: confined to workspace, content ≤ 1,000,000 chars, creates parent dirs, returns `wrote <rel>`
    8. `run_command`: `executor.run(argv, ctx.workspace, timeout_s)`; code ≠ 0 → `error`, `command failed (exit <code>): <stderr[:2000]>`; `ExecutorError` → `error`, `command failed: <message>`; else stdout
    9. `host_query`: `error`, `host_query is not available yet`
    10. every text cut to 20,000 chars
  - keep each handler a private method ≤ 40 lines; complexity ≤ 10
- verify: `cd engine && uv run python -c "from limo.agents.tools import ToolBox, TOOL_SPECS; print(sorted(TOOL_SPECS))"` → the 7 tool names

### STEP-10 run models and repo
- file: `engine/limo/agents/models.py` (edit), `engine/limo/agents/repo.py` (create)
- do:
  - models: add `RunIn` (`extra="forbid"`; `agent: Literal["architecture", "spec", "plan", "build", "verify", "close", "resolver"]`; `feature` pattern; `ticket: str | None = Field(default=None, pattern=r"^TKT-\d+$")`), `Run` (fields per contracts), `ToolCall` (fields per contracts)
  - repo `RunRepo(db_path)`: `insert(run: Run, project_id: str)`, `get(run_id) -> Run | None` (join `projects` for the project name), `set_status(run_id, status)`, `finish(run_id, status, output, error)` (sets `finished_at`), `add_tool_call(run_id, seq, outcome_name, target, status, summary)`, `tool_calls(run_id) -> list[ToolCall]`. One connection per method, like `projects/repo.py`.
- verify: `cd engine && uv run python -c "import limo.agents.repo"` → exit 0

### STEP-11 run service
- file: `engine/limo/agents/service.py` (create)
- do: `RunService(runs: RunRepo, projects: ProjectRepo, llm: LlmClient, tools: ToolBox, skills_dir: Path, settings_model: str, max_turns: int, pool: ThreadPoolExecutor)`:
  - `start(project_name, data: RunIn) -> Run`: project missing → `NotFound("project_not_found", …)`; insert `queued` run (`model=settings_model`); `pool.submit(self._execute, run_id)`; return run
  - `get(run_id)` / `tool_calls(run_id)`: missing → `NotFound("run_not_found", …)`
  - `_execute(run_id)`: top-level guard — any exception → `finish(failed, error=f"internal_error: {e}")`; `LlmError` → `finish(failed, error=f"llm_error: {e}")`
  - loop (put in `_loop`, ≤ 40 lines):
```python
system = (self._skills_dir / run.agent / "SKILL.md").read_text()
task = f"feature={run.feature} ticket={run.ticket}" if run.ticket else f"feature={run.feature}"
messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
for _ in range(self._max_turns):
    resp = self._llm.create(LlmRequest(run.model, system, list(messages), self._tools.specs(run.agent)))
    messages.append({"role": "assistant", "content": resp.content})
    uses = [b for b in resp.content if b.get("type") == "tool_use"]
    if resp.stop_reason != "tool_use" or not uses:
        text = "\n".join(b["text"] for b in resp.content if b.get("type") == "text")
        ok = resp.stop_reason == "end_turn"
        return self._runs.finish(run.id, "succeeded" if ok else "failed", text, None if ok else f"stop: {resp.stop_reason}")
    messages.append({"role": "user", "content": [self._tool_result(run, ctx, u) for u in uses]})
self._runs.finish(run.id, "failed", None, "max turns reached")
```
  - `ctx` = `ToolContext(agent, workspace, skills_dir / agent, readable)`; `readable` for `build` = `parse_context_pack(plan)` plus `{f"work/{feature}/plans/{ticket}.md": None, "context/INDEX.md": None}`; plan missing → finish failed `plan not found: <path>`; other agents → `None`
  - `_tool_result(run, ctx, use)`: `outcome = tools.call(ctx, use["name"], use["input"])`; record tool call (seq = running count); return `{"type": "tool_result", "tool_use_id": use["id"], "content": outcome.text, "is_error": outcome.status != "ok"}`
  - pass `list(messages)` (a copy) to the LLM so recorded requests do not change later
- verify: `cd engine && uv run python -c "import limo.agents.service"` → exit 0

### STEP-12 API and wiring
- file: `engine/limo/api/runs_routes.py` (create), `engine/limo/app.py` (edit)
- do:
  - `runs_router(service: RunService) -> APIRouter` (no prefix): `POST /api/projects/{name}/runs` (202, `Run`), `GET /api/runs/{run_id}` (`Run`), `GET /api/runs/{run_id}/tool-calls` (`list[ToolCall]`); plain `def` handlers
  - `app.py`: `Deps` gains `llm: LlmClient`; default `Deps(executor=LocalExecutor(), llm=AnthropicLlm(settings.anthropic_api_key))`; create `pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="limo-run")`; build `RunService(RunRepo(db), ProjectRepo(db), deps.llm, ToolBox(deps.executor, settings.command_timeout_s), settings.skills_dir, settings.default_model, settings.max_turns, pool)`; include the router; shut the pool down in a FastAPI `lifespan` (`yield` then `pool.shutdown(wait=True, cancel_futures=True)`)
- verify: `mise run test:engine` → all FT-1.* and FT-2.* pass

### STEP-13 import contract
- file: `engine/pyproject.toml` (edit)
- do: in the existing contract append `"limo.llm.anthropic_client"` to `forbidden_modules`
- verify: `mise run arch` → `Contracts: 1 kept, 0 broken.`

### STEP-14 format, gates, full suite
- file: none new (edit only lines a gate reports, in files this plan created or edited)
- do: `mise run fmt`, then `mise run gates`, then `mise run test`
- verify: gates exit 0; `mise run test` → all passed (14 from TKT-1 + 16 from TKT-2 incl. parametrized cases count as reported)

## Do not
- add usage/cost recording, model-per-agent settings, runner logic, SSE, or UI
- give any agent a tool outside its allowlist above; give `host_query` a real implementation
- put the API key, `.env` values, or workspace `CLAUDE.md` into any request
- call `subprocess` outside `limo/executor/local.py` and `tests/`

## Doc updates
- context/INDEX.md: Shape — add `engine/limo/llm` — LLM port + Anthropic adapter → Claude API (HTTPS); `agents` line: registry + run loop + tools (no longer planned)
- context/layout.md: Tree module list adds `llm`; Where to put new things — agent tool → `engine/limo/agents/tools.py` (one handler method + TOOL_SPECS entry + ALLOWLISTS); fake → `engine/tests/fakes/llm.py`
- context/api.md: Reference implementations — runs: `engine/limo/api/runs_routes.py`
- context/data.md: Main entities — `runs` and `tool_calls` columns as in `002_runs.sql`
- context/security.md: Agent tools — enforced in `engine/limo/agents/tools.py` (`ToolBox.call`); allowlists in `engine/limo/agents/allowlists.py`
- context/testing.md: Fakes — Claude Messages API fake exists at `engine/tests/fakes/llm.py` (`FakeLlm`, `tool_use`, `final`); helpers `add_cart_project`, `start_and_wait` in `engine/tests/builders.py`
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
