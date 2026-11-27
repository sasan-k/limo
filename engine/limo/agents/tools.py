import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from limo.agents.allowlists import ALLOWLISTS
from limo.executor.ports import Executor, ExecutorError

MAX_TEXT = 20_000
MAX_LIST = 200
MAX_MATCHES = 50
MAX_LINE = 200  # chars per grep match line; results stay in the agent's context every later turn
MAX_WRITE = 1_000_000
MAX_STDERR = 2_000


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    schema = {"type": "object", "properties": properties, "required": required}
    return {"name": name, "description": description, "input_schema": schema}


_STR = {"type": "string"}
_INT = {"type": "integer"}

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "read_file": _tool(
        "read_file",
        "Read a text file in the workspace.",
        {"path": _STR, "start_line": _INT, "end_line": _INT},
        ["path"],
    ),
    "list_files": _tool("list_files", "List a workspace directory.", {"path": _STR}, ["path"]),
    "grep": _tool(
        "grep", "Search workspace files for a Python regex.", {"pattern": _STR, "path": _STR}, ["pattern"]
    ),
    "read_ref": _tool(
        "read_ref", "Read a reference file of the agent's skill directory.", {"path": _STR}, ["path"]
    ),
    "write_file": _tool(
        "write_file",
        "Write a text file in the workspace.",
        {"path": _STR, "content": _STR},
        ["path", "content"],
    ),
    "run_command": _tool(
        "run_command",
        "Run a command given as an argv list (no shell) in the workspace.",
        {"argv": {"type": "array", "items": _STR}},
        ["argv"],
    ),
    "host_query": _tool("host_query", "Query the code host.", {"query": _STR}, ["query"]),
}


@dataclass(frozen=True)
class ToolContext:
    agent: str
    workspace: Path
    agent_dir: Path
    readable: dict[str, tuple[int, int] | None] | None
    env: dict[str, str]


@dataclass(frozen=True)
class ToolOutcome:
    text: str
    status: Literal["ok", "error", "rejected"]
    target: str


class _InvalidInput(Exception):
    pass


def _str(tool_input: dict[str, Any], key: str) -> str:
    value = tool_input.get(key)
    if not isinstance(value, str):
        raise _InvalidInput(f"{key} required")
    return value


def _opt_str(tool_input: dict[str, Any], key: str, default: str) -> str:
    value = tool_input.get(key, default)
    if not isinstance(value, str):
        raise _InvalidInput(f"{key} must be a string")
    return value


def _opt_int(tool_input: dict[str, Any], key: str, default: int) -> int:
    value = tool_input.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise _InvalidInput(f"{key} must be an integer")
    return value


def _confine(root: Path, rel: str) -> Path | None:
    """Resolve `rel` under `root`; None when it escapes `root`."""
    target = (root / rel).resolve()
    return target if target.is_relative_to(root.resolve()) else None


def _outside(rel: str, label: str) -> ToolOutcome:
    return ToolOutcome(f"path {label}: {rel}", "rejected", rel)


def _grep_lines(file: Path, base: Path, regex: re.Pattern[str]) -> list[str]:
    try:
        lines = file.read_text().splitlines()
    except UnicodeDecodeError:
        return []
    name = file.relative_to(base).as_posix()
    return [f"{name}:{n}: {line[:MAX_LINE]}" for n, line in enumerate(lines, 1) if regex.search(line)]


class ToolBox:
    def __init__(self, executor: Executor, timeout_s: float) -> None:
        self._executor = executor
        self._timeout_s = timeout_s
        self._handlers: dict[str, Callable[[ToolContext, dict[str, Any]], ToolOutcome]] = {
            "read_file": self._read_file,
            "list_files": self._list_files,
            "grep": self._grep,
            "read_ref": self._read_ref,
            "write_file": self._write_file,
            "run_command": self._run_command,
            "host_query": self._host_query,
        }

    def specs(self, agent: str) -> list[dict[str, Any]]:
        return [TOOL_SPECS[name] for name in ALLOWLISTS[agent]]

    def call(self, ctx: ToolContext, name: str, tool_input: dict[str, Any]) -> ToolOutcome:
        if name not in ALLOWLISTS[ctx.agent]:
            return ToolOutcome(f"tool not allowed: {name}", "rejected", name)
        try:
            outcome = self._handlers[name](ctx, tool_input)
        except _InvalidInput as e:
            outcome = ToolOutcome(f"invalid input: {e}", "error", name)
        return replace(outcome, text=outcome.text[:MAX_TEXT])

    def _read_file(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        rel = _str(tool_input, "path")
        path = _confine(ctx.workspace, rel)
        if path is None:
            return _outside(rel, "outside workspace")
        if ctx.readable is not None and rel not in ctx.readable:
            return ToolOutcome(f"not in context pack: {rel}", "rejected", rel)
        if not path.is_file():
            return ToolOutcome(f"file not found: {rel}", "error", rel)
        lines = path.read_text().splitlines(keepends=True)
        pack = ctx.readable.get(rel) if ctx.readable is not None else None
        start, end = pack or (
            _opt_int(tool_input, "start_line", 1),
            _opt_int(tool_input, "end_line", len(lines)),
        )
        return ToolOutcome("".join(lines[start - 1 : end]), "ok", rel)

    def _list_files(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        rel = _str(tool_input, "path")
        path = _confine(ctx.workspace, rel)
        if path is None:
            return _outside(rel, "outside workspace")
        if not path.is_dir():
            return ToolOutcome(f"not a directory: {rel}", "error", rel)
        names = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
        return ToolOutcome("\n".join(names[:MAX_LIST]), "ok", rel)

    def _grep(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        pattern = _str(tool_input, "pattern")
        rel = _opt_str(tool_input, "path", ".")
        root = _confine(ctx.workspace, rel)
        if root is None:
            return _outside(rel, "outside workspace")
        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise _InvalidInput(f"pattern is not a valid regex: {e}") from e
        base = ctx.workspace.resolve()
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        matches: list[str] = []
        for file in files:
            if file.is_file() and ".git" not in file.relative_to(base).parts:
                matches.extend(_grep_lines(file, base, regex))
        shown = matches[:MAX_MATCHES]
        if len(matches) > MAX_MATCHES:
            shown.append(f"... {len(matches) - MAX_MATCHES} more matches; narrow the pattern or path")
        return ToolOutcome("\n".join(shown), "ok", pattern)

    def _read_ref(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        rel = _str(tool_input, "path")
        path = _confine(ctx.agent_dir, rel)
        if path is None:
            return _outside(rel, "outside agent dir")
        if not path.is_file():
            return ToolOutcome(f"file not found: {rel}", "error", rel)
        return ToolOutcome(path.read_text(), "ok", rel)

    def _write_file(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        rel = _str(tool_input, "path")
        content = _str(tool_input, "content")
        path = _confine(ctx.workspace, rel)
        if path is None:
            return _outside(rel, "outside workspace")
        if len(content) > MAX_WRITE:
            return ToolOutcome(f"content too large: {rel}", "error", rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ToolOutcome(f"wrote {rel}", "ok", rel)

    def _run_command(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        argv = tool_input.get("argv")
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise _InvalidInput("argv required")
        target = " ".join(argv)
        try:
            result = self._executor.run(argv, ctx.workspace, self._timeout_s, env=ctx.env)
        except ExecutorError as e:
            return ToolOutcome(f"command failed: {e}", "error", target)
        if result.code != 0:
            text = f"command failed (exit {result.code}): {result.stderr[:MAX_STDERR]}"
            return ToolOutcome(text, "error", target)
        return ToolOutcome(result.stdout, "ok", target)

    def _host_query(self, ctx: ToolContext, tool_input: dict[str, Any]) -> ToolOutcome:
        query = _str(tool_input, "query")
        return ToolOutcome("host_query is not available yet", "error", query)
