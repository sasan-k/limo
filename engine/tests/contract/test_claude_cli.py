"""ClaudeCli adapter against a fake `claude` binary (ADR-14): flags, environment, stream-json parsing."""

import json
from pathlib import Path
from typing import Any

import pytest

from limo.llm.claude_cli import ClaudeCli
from limo.llm.ports import CliRequest, LlmError, LlmUsage

FAKE = Path(__file__).resolve().parents[1] / "fakes" / "fake_claude.py"


def _request(tmp_path: Path, task: str, timeout_s: float = 10.0, budget: float | None = 2.5) -> CliRequest:
    return CliRequest(
        model="claude-haiku-5-5",
        task=task,
        system_prompt_file=tmp_path / "SKILL.md",
        mcp_config_file=tmp_path / "mcp.json",
        cwd=tmp_path / "cwd",
        timeout_s=timeout_s,
        max_budget_usd=budget,
    )


def _seen(tmp_path: Path) -> dict[str, Any]:
    return dict(json.loads((tmp_path / "cwd" / "seen.json").read_text()))


def test_runs_claude_with_no_user_setup_and_only_limo_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """argv carries every isolation flag; env has only PATH and HOME (no API key leaks)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-pass")
    events: list[dict[str, Any]] = []
    result = ClaudeCli(str(FAKE)).run(_request(tmp_path, "ok"), events.append)
    argv = _seen(tmp_path)["argv"]
    assert argv[:2] == ["-p", "ok"]
    pairs = {
        "--system-prompt-file": str(tmp_path / "SKILL.md"),
        "--model": "claude-haiku-5-5",
        "--tools": "",
        "--setting-sources": "",
        "--mcp-config": str(tmp_path / "mcp.json"),
        "--allowedTools": "mcp__limo",
        "--permission-mode": "dontAsk",
        "--output-format": "stream-json",
        "--max-budget-usd": "2.50",
    }
    for flag, value in pairs.items():
        assert argv[argv.index(flag) + 1] == value
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--verbose"):
        assert flag in argv
    assert "--safe-mode" not in argv and "--bare" not in argv
    assert set(_seen(tmp_path)["env"]) - {"LC_CTYPE"} == {"HOME", "PATH"}  # LC_CTYPE: python locale coercion
    assert result.ok is True
    assert result.text == "all done"
    assert result.usage == LlmUsage(12, 34, 56, 78)
    assert result.cost_micros == 42_100
    assert [e["type"] for e in events] == ["system", "assistant", "result"]


def test_no_budget_flag_without_a_ticket_budget(tmp_path: Path) -> None:
    ClaudeCli(str(FAKE)).run(_request(tmp_path, "ok", budget=None), lambda e: None)
    assert "--max-budget-usd" not in _seen(tmp_path)["argv"]


def test_error_result_and_crash_are_failures(tmp_path: Path) -> None:
    """An error result keeps its subtype; a crash without a result reports stderr."""
    failed = ClaudeCli(str(FAKE)).run(_request(tmp_path, "error"), lambda e: None)
    assert failed.ok is False
    assert failed.error == "cli: error_max_budget_usd: all done"
    assert failed.cost_micros == 42_100
    crashed = ClaudeCli(str(FAKE)).run(_request(tmp_path, "crash"), lambda e: None)
    assert crashed.ok is False
    assert crashed.error == "cli: Not logged in. Run claude /login"


def test_timeout_kills_the_session(tmp_path: Path) -> None:
    result = ClaudeCli(str(FAKE)).run(_request(tmp_path, "sleep", timeout_s=0.5), lambda e: None)
    assert result.ok is False
    assert result.error == "cli: timeout"


def test_missing_binary_is_an_llm_error(tmp_path: Path) -> None:
    with pytest.raises(LlmError, match="claude CLI not found"):
        ClaudeCli(str(tmp_path / "no-such-claude")).run(_request(tmp_path, "ok"), lambda e: None)
