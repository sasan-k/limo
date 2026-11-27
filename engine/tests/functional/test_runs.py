import dataclasses
import json
from pathlib import Path

from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.llm.ports import LlmError
from tests.builders import add_cart_project, start_and_wait
from tests.fakes.llm import FakeLlm, tool_use


def test_ft_2_1_run_gets_only_prompt_task_and_tools(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.1 `plan` run: request holds skill prompt, task and plan tools only; no secret or CLAUDE.md."""
    add_cart_project(client, tmp_path)
    run = start_and_wait(client, "plan", "TKT-1")
    assert run["status"] == "succeeded"
    request = llm.requests[0]
    expected_system = (Settings(_env_file=None).skills_dir / "plan" / "SKILL.md").read_text()
    assert request.system == expected_system
    assert request.messages[0] == {"role": "user", "content": "feature=cart ticket=TKT-1"}
    names = [t["name"] for t in request.tools]
    assert names == ["read_file", "list_files", "grep", "read_ref", "write_file", "run_command"]
    dumped = json.dumps(dataclasses.asdict(request))
    assert "secret house rules" not in dumped
    assert "sk-canary-123" not in dumped


def test_ft_2_5_resolver_tools_are_read_only_plus_host_query(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-2.5 `resolver` run offers exactly the resolver allowlist in order."""
    add_cart_project(client, tmp_path)
    start_and_wait(client, "resolver")
    assert [t["name"] for t in llm.requests[0].tools] == ["read_file", "list_files", "grep", "host_query"]


def test_ft_2_6_invalid_run_bodies_are_rejected(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.6 unknown agent, malformed ticket and extra field each give 422 validation_error."""
    add_cart_project(client, tmp_path)
    bodies = [
        {"agent": "deploy", "feature": "cart", "ticket": None},
        {"agent": "plan", "feature": "cart", "ticket": "T1"},
        {"agent": "plan", "feature": "cart", "ticket": None, "model": "x"},
    ]
    for body in bodies:
        r = client.post("/api/projects/shop/runs", json=body)
        assert r.status_code == 422
        assert "validation_error" in r.text


def test_ft_2_7_run_on_unknown_project_is_not_found(client: TestClient, llm: FakeLlm) -> None:
    """FT-2.7 POST run on project `nope` gives 404 project_not_found."""
    r = client.post("/api/projects/nope/runs", json={"agent": "plan", "feature": "cart", "ticket": None})
    assert r.status_code == 404
    assert "project_not_found" in r.text


def test_ft_2_8_unknown_run_is_not_found(client: TestClient, llm: FakeLlm) -> None:
    """FT-2.8 GET of an unknown run and its tool calls give 404 run_not_found."""
    assert client.get("/api/runs/missing").status_code == 404
    assert "run_not_found" in client.get("/api/runs/missing").text
    r = client.get("/api/runs/missing/tool-calls")
    assert r.status_code == 404
    assert "run_not_found" in r.text


def test_ft_2_9_llm_failure_fails_the_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-2.9 LLM error marks the run failed with an llm_error prefix."""
    add_cart_project(client, tmp_path)
    llm.fail_with = LlmError("overloaded")
    run = start_and_wait(client, "plan", "TKT-1")
    assert run["status"] == "failed"
    assert run["error"].startswith("llm_error:")


def test_ft_2_14_max_turns_stops_the_loop(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-2.14 a model that never stops is cut off after max_turns requests and the run fails."""
    settings = Settings(data_dir=tmp_path / "data", max_turns=3, _env_file=None)
    llm.repeat = lambda: tool_use("list_files", {"path": "."})
    deps = Deps(LocalExecutor(path_prefix=settings.scripts_dir), llm)
    with TestClient(create_app(settings, deps)) as client:
        add_cart_project(client, tmp_path)
        run = start_and_wait(client, "plan", "TKT-1")
    assert run["status"] == "failed"
    assert run["error"] == "max turns reached"
    assert len(llm.requests) == 3
