import json
import os
import subprocess
import threading
from collections.abc import Callable
from typing import Any

from limo.llm.ports import CliRequest, CliResult, LlmError, LlmUsage

MAX_ERROR = 500


def build_argv(binary: str, request: CliRequest) -> list[str]:
    """`claude -p` with no user setup, no built-in tools, and only the run's Limo MCP server (ADR-14)."""
    argv = [
        binary,
        "-p",
        request.task,
        "--system-prompt-file",
        str(request.system_prompt_file),
        "--model",
        request.model,
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(request.mcp_config_file),
        "--allowedTools",
        "mcp__limo",
        "--permission-mode",
        "dontAsk",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if request.max_budget_usd is not None:
        argv += ["--max-budget-usd", f"{request.max_budget_usd:.2f}"]
    return argv


def _usage(raw: dict[str, Any]) -> LlmUsage:
    return LlmUsage(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_read_tokens=int(raw.get("cache_read_input_tokens") or 0),
        cache_write_tokens=int(raw.get("cache_creation_input_tokens") or 0),
    )


def parse_result(event: dict[str, Any]) -> CliResult:
    """Map the final `result` stream-json event to a CliResult."""
    text = str(event.get("result") or "")
    ok = event.get("subtype") == "success" and not event.get("is_error")
    error = None if ok else f"cli: {event.get('subtype', 'error')}: {text[:MAX_ERROR]}"
    cost = round(float(event.get("total_cost_usd") or 0) * 1_000_000)
    return CliResult(ok=ok, text=text, error=error, usage=_usage(event.get("usage") or {}), cost_micros=cost)


class ClaudeCli:
    """AgentCli adapter: runs the local `claude` binary with the user's own login (ADR-14)."""

    def __init__(self, binary: str) -> None:
        self._binary = binary

    def run(self, request: CliRequest, on_event: Callable[[dict[str, Any]], None]) -> CliResult:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
        request.cwd.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.Popen(
                build_argv(self._binary, request),
                cwd=request.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as e:
            raise LlmError(f"claude CLI not found or not runnable: {self._binary}") from e
        errors: list[str] = []
        drain = threading.Thread(target=lambda: errors.extend(proc.stderr or []), daemon=True)
        drain.start()
        timer = threading.Timer(request.timeout_s, proc.kill)
        timer.start()
        try:
            result = self._read(proc, on_event)
            code = proc.wait()
        finally:
            timer.cancel()
        drain.join(timeout=5)
        stderr = "".join(errors)
        if result is not None:
            return result
        reason = "timeout" if code < 0 else (stderr.strip() or f"exit code {code}")
        return CliResult(
            ok=False, text="", error=f"cli: {reason[-MAX_ERROR:]}", usage=LlmUsage(), cost_micros=0
        )

    @staticmethod
    def _read(proc: "subprocess.Popen[str]", on_event: Callable[[dict[str, Any]], None]) -> CliResult | None:
        result: CliResult | None = None
        for line in proc.stdout or []:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            on_event(event)
            if event.get("type") == "result":
                result = parse_result(event)
        return result
