from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import add_cart_project, start_and_wait, write_workspace_file
from tests.fakes.llm import FakeLlm, tool_use


def _first_tool_result(llm: FakeLlm) -> dict[str, Any]:
    return llm.requests[1].messages[-1]["content"][0]


def test_ft_2_2_disallowed_tool_is_rejected_and_recorded(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-2.2 verify calling write_file gets a rejected tool_result and a rejected tool call row."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("write_file", {"path": "x.txt", "content": "y"})]
    run = start_and_wait(client, "verify")
    assert run["status"] == "succeeded"
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"] == "tool not allowed: write_file"
    calls = client.get(f"/api/runs/{run['id']}/tool-calls").json()
    assert [(c["seq"], c["name"], c["status"]) for c in calls] == [(1, "write_file", "rejected")]


def test_ft_2_3_build_reads_file_in_context_pack(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.3 build reading src/cart.py (in the context pack) gets its content."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("read_file", {"path": "src/cart.py"})]
    start_and_wait(client, "build")
    result = _first_tool_result(llm)
    assert result["content"] == "def total() -> int:\n    return 0\n"
    assert result["is_error"] is False


def test_ft_2_4_build_cannot_read_file_outside_context_pack(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-2.4 build reading src/payment.py (not in the context pack) is rejected."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("read_file", {"path": "src/payment.py"})]
    run = start_and_wait(client, "build")
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"] == "not in context pack: src/payment.py"
    calls = client.get(f"/api/runs/{run['id']}/tool-calls").json()
    assert calls[0]["status"] == "rejected"


def test_ft_2_10_path_escape_is_rejected(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.10 read_file with a path leaving the workspace is rejected."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("read_file", {"path": "../outside.txt"})]
    start_and_wait(client, "plan")
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"] == "path outside workspace: ../outside.txt"


def test_ft_2_11_missing_file_is_an_error(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.11 read_file of a missing file gives an error tool_result and an error tool call."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("read_file", {"path": "src/nope.py"})]
    run = start_and_wait(client, "plan")
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"] == "file not found: src/nope.py"
    calls = client.get(f"/api/runs/{run['id']}/tool-calls").json()
    assert calls[0]["status"] == "error"


def test_ft_2_12_invalid_tool_input_is_an_error(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.12 read_file without its required path gives invalid input."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("read_file", {})]
    start_and_wait(client, "plan")
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"].startswith("invalid input:")


def test_ft_2_13_failing_command_is_an_error(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.13 run_command exiting non-zero gives an error tool_result with the exit code."""
    add_cart_project(client, tmp_path)
    llm.script = [tool_use("run_command", {"argv": ["false"]})]
    start_and_wait(client, "build")
    result = _first_tool_result(llm)
    assert result["is_error"] is True
    assert result["content"].startswith("command failed (exit 1)")


def test_grep_results_are_capped_and_lines_shortened(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """grep returns at most 50 matches, each line cut to 200 chars, plus a note on how many were left out."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "notes.txt", "".join(f"match {'x' * 300}\n" for _ in range(60)))
    llm.script = [tool_use("grep", {"pattern": "^match", "path": "notes.txt"})]
    start_and_wait(client, "plan")
    lines = _first_tool_result(llm)["content"].splitlines()
    assert len(lines) == 51
    assert all(len(line) <= len("notes.txt:60: ") + 200 for line in lines[:50])
    assert lines[-1] == "... 10 more matches; narrow the pattern or path"


RANGE_PLAN = """# TKT-1

## Context pack
- `src/cart.py:2-2` — range inside the backticks
- `src/payment.py`:1-1 — range after the backticks
- `notes.txt:2-3,5-6` — several ranges inside the backticks

## Steps
"""


def test_context_pack_line_ranges_inside_or_after_backticks(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """Build may read files whose pack entry has a range inside or after the backticks; several ranges
    read as one span from the first start to the last end."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "work/cart/plans/TKT-1.md", RANGE_PLAN)
    write_workspace_file(settings, "shop", "notes.txt", "".join(f"line {n}\n" for n in range(1, 9)))
    llm.script = [
        tool_use("read_file", {"path": "src/cart.py"}, "tu_1"),
        tool_use("read_file", {"path": "src/payment.py"}, "tu_2"),
        tool_use("read_file", {"path": "notes.txt"}, "tu_3"),
    ]
    start_and_wait(client, "build")
    results = [r.messages[-1]["content"][0] for r in llm.requests[1:4]]
    assert [r["is_error"] for r in results] == [False, False, False]
    assert results[0]["content"] == "    return 0\n"
    assert results[1]["content"] == "SECRET = 1\n"
    assert results[2]["content"] == "line 2\nline 3\nline 4\nline 5\nline 6\n"
