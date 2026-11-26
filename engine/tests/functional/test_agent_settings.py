from pathlib import Path

from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import add_cart_project, start_and_wait
from tests.fakes.llm import FakeLlm


def test_ft_3_1_set_and_list_model(client: TestClient, settings: Settings) -> None:
    """FT-3.1 set build model; list shows it and default for the others."""
    r = client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"})
    assert r.status_code == 200
    assert r.json()["model"] == "claude-haiku-5-5"
    agents = {a["name"]: a for a in client.get("/api/agents").json()}
    assert agents["build"]["model"] == "claude-haiku-5-5"
    assert agents["plan"]["model"] == settings.default_model


def test_ft_3_2_run_keeps_model_at_start(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-3.2 a run keeps the model it was started with."""
    add_cart_project(client, tmp_path)
    assert client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"}).status_code == 200
    run = start_and_wait(client, "build")
    assert llm.requests[0].model == "claude-haiku-5-5"
    assert run["model"] == "claude-haiku-5-5"
    assert client.put("/api/agents/build/model", json={"model": "claude-sonnet-5-5"}).status_code == 200
    stored = client.get(f"/api/runs/{run['id']}").json()
    assert stored["model"] == "claude-haiku-5-5"


def test_ft_3_3_rejects_invalid_model_bodies(client: TestClient) -> None:
    """FT-3.3 invalid bodies give 422 validation_error."""
    bodies = [{"model": "Claude Haiku!"}, {"model": "x", "temperature": 1}, {}]
    for body in bodies:
        r = client.put("/api/agents/build/model", json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["code"] == "validation_error", body


def test_ft_3_4_unknown_agent_not_found(client: TestClient) -> None:
    """FT-3.4 unknown agent gives 404 agent_not_found."""
    r = client.put("/api/agents/deploy/model", json={"model": "claude-haiku-5-5"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "agent_not_found"


def test_ft_3_5_same_model_twice_is_idempotent(client: TestClient) -> None:
    """FT-3.5 setting the same model twice gives the same body and one entry."""
    first = client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"})
    second = client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    agents = [a for a in client.get("/api/agents").json() if a["name"] == "build"]
    assert len(agents) == 1
    assert agents[0]["model"] == "claude-haiku-5-5"


def test_ft_3_6_model_length_boundary(client: TestClient) -> None:
    """FT-3.6 64 chars accepted, 65 chars rejected."""
    assert client.put("/api/agents/build/model", json={"model": "a" * 64}).status_code == 200
    assert client.put("/api/agents/build/model", json={"model": "a" * 65}).status_code == 422


def test_ft_3_7_all_agents_default_model(client: TestClient, settings: Settings) -> None:
    """FT-3.7 with nothing set, all 7 agents use the default model."""
    agents = client.get("/api/agents").json()
    assert len(agents) == 7
    assert all(a["model"] == settings.default_model for a in agents)
