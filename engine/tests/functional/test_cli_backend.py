"""Agents as local `claude -p` sessions with tools only from Limo's per-run MCP endpoint (ADR-14)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.llm.ports import CliResult, LlmError, LlmUsage
from tests.builders import add_cart_project, start_and_wait, wait_run
from tests.fakes.cli import FakeCli, SeenRun
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        agent_backend="claude-cli",
        agent_cwd=tmp_path / "agent-cwd",
        anthropic_api_key="sk-canary-123",
        _env_file=None,
    )


@pytest.fixture
def cli() -> FakeCli:
    return FakeCli()


@pytest.fixture
def client(settings: Settings, llm: FakeLlm, cli: FakeCli) -> Iterator[TestClient]:
    deps = Deps(LocalExecutor(path_prefix=settings.scripts_dir), llm, FakeHost(), cli=cli)
    with TestClient(create_app(settings, deps)) as c:
        yield c


def _rpc(client: TestClient, seen: SeenRun, method: str, params: dict[str, Any] | None = None) -> Any:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    r = client.post(seen.mcp_path, json=body, headers={"Authorization": seen.auth})
    assert r.status_code == 200
    return r.json()


def _call(client: TestClient, seen: SeenRun, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return dict(_rpc(client, seen, "tools/call", {"name": name, "arguments": arguments})["result"])


def test_cli_run_is_an_isolated_claude_session(
    client: TestClient, llm: FakeLlm, cli: FakeCli, settings: Settings, tmp_path: Path
) -> None:
    """A plan run starts one CLI session with the agent's prompt, the task, the budget left and a
    private MCP config; the API is not used; billed tokens and cost are recorded."""
    add_cart_project(client, tmp_path)
    cli.result = CliResult(
        ok=True, text="planned", error=None, usage=LlmUsage(1000, 200, 300, 400), cost_micros=123_456
    )
    run = start_and_wait(client, "plan")
    assert llm.requests == []
    seen = cli.seen[0]
    assert seen.request.model == "claude-opus-5-5"
    assert seen.request.task == "feature=cart ticket=TKT-1"
    assert seen.system_prompt == (settings.skills_dir / "plan" / "SKILL.md").read_text()
    assert seen.request.cwd == settings.agent_cwd
    assert seen.request.max_budget_usd == 5.0
    assert seen.mcp["mcpServers"]["limo"]["url"] == f"{settings.engine_url}/mcp/runs/{run['id']}"
    assert seen.auth.startswith("Bearer ") and len(seen.auth) > 30
    assert seen.mcp_file_mode == 0o600
    assert not seen.request.mcp_config_file.exists()
    assert run["status"] == "succeeded"
    assert run["output"] == "planned"
    assert run["tokens"] == {"input": 1000, "output": 200, "cache_read": 300, "cache_write": 400}
    assert run["cost"] == "0.123456"


def test_mcp_endpoint_serves_only_the_allowlist_and_records_calls(
    client: TestClient, cli: FakeCli, tmp_path: Path
) -> None:
    """While a build session runs, its MCP endpoint lists only build tools, enforces the context pack
    and the allowlist, records every call, and rejects bad or expired tokens."""
    add_cart_project(client, tmp_path)
    cli.hold = True
    r = client.post("/api/projects/shop/runs", json={"agent": "build", "feature": "cart", "ticket": "TKT-1"})
    assert cli.started.wait(5)
    seen = cli.seen[0]
    init = _rpc(client, seen, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}})
    assert init["result"]["protocolVersion"] == "2025-11-25"
    note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert client.post(seen.mcp_path, json=note, headers={"Authorization": seen.auth}).status_code == 202
    tools = [t["name"] for t in _rpc(client, seen, "tools/list")["result"]["tools"]]
    assert tools == ["read_file", "read_ref", "write_file", "run_command"]
    ok = _call(client, seen, "read_file", {"path": "src/cart.py"})
    assert ok["isError"] is False and "def total" in ok["content"][0]["text"]
    assert _call(client, seen, "read_file", {"path": "src/payment.py"})["isError"] is True
    assert _call(client, seen, "grep", {"pattern": "SECRET"})["isError"] is True
    assert _rpc(client, seen, "resources/list")["error"]["code"] == -32601
    bad = client.post(seen.mcp_path, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "mcp_unauthorized"
    cli.release.set()
    run_id = r.json()["id"]
    assert wait_run(client, run_id)["status"] == "succeeded"
    calls = client.get(f"/api/runs/{run_id}/tool-calls").json()
    assert [(c["name"], c["status"]) for c in calls] == [
        ("read_file", "ok"),
        ("read_file", "rejected"),
        ("grep", "rejected"),
    ]
    late = client.post(
        seen.mcp_path,
        json={"jsonrpc": "2.0", "id": 3, "method": "ping"},
        headers={"Authorization": seen.auth},
    )
    assert late.status_code == 401


def test_cli_failures_fail_the_run(client: TestClient, cli: FakeCli, tmp_path: Path) -> None:
    """A session that ends in error, or a missing `claude` binary, fails the run with the reason."""
    add_cart_project(client, tmp_path)
    cli.result = CliResult(
        ok=False, text="", error="cli: error_max_budget_usd: stopped", usage=LlmUsage(), cost_micros=0
    )
    assert start_and_wait(client, "plan")["error"] == "cli: error_max_budget_usd: stopped"
    cli.fail_with = LlmError("claude CLI not found or not runnable: claude")
    failed = start_and_wait(client, "plan")
    assert failed["status"] == "failed"
    assert failed["error"] == "llm_error: claude CLI not found or not runnable: claude"


def test_spent_budget_holds_the_ticket_without_starting_a_session(
    client: TestClient, cli: FakeCli, tmp_path: Path
) -> None:
    """When the agent's budget on the ticket is used up, no CLI session starts and the ticket is held."""
    add_cart_project(client, tmp_path)
    cli.result = CliResult(ok=True, text="done", error=None, usage=LlmUsage(10, 10), cost_micros=5_000_000)
    start_and_wait(client, "plan")
    second = start_and_wait(client, "plan")
    assert len(cli.seen) == 1
    assert second["status"] == "failed"
    assert second["error"].startswith("budget: plan budget reached")
    holds = [i for i in client.get("/api/inbox").json() if i["kind"] == "budget"]
    assert [h["ticket"] for h in holds] == ["TKT-1"]
