from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.common.constants import AGENT_NAMES
from limo.config import Settings
from limo.llm.ports import LlmError, LlmUsage
from tests.builders import add_cart_project, next_event, start_and_wait, wait_run
from tests.fakes.llm import FakeLlm, blocking_build, final_with


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", sse_heartbeat_s=0.2, _env_file=None
    )


def _card(client: TestClient, agent: str) -> dict[str, Any]:
    return next(c for c in client.get("/api/agent-cards").json() if c["agent"] == agent)


def test_ft_12_1_card_shows_model_state_ticket_cost_last_run(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-12.1 card shows model, state, ticket, cost and last run (SC-40)."""
    add_cart_project(client, tmp_path)
    assert client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"}).status_code == 200
    assert client.put("/api/prices/claude-haiku-5-5", json={"input": 4, "output": 20}).status_code == 200
    llm.script = [final_with(LlmUsage(40_000, 12_000))]
    run = start_and_wait(client, "build")

    r = client.get("/api/agent-cards")
    assert r.status_code == 200
    body = r.json()
    assert [c["agent"] for c in body] == list(AGENT_NAMES)

    build = _card(client, "build")
    assert build["model"] == "claude-haiku-5-5"
    assert build["state"] == "idle"
    assert build["project"] == "shop"
    assert build["feature"] == "cart"
    assert build["ticket"] == "TKT-1"
    assert build["cost"] == "0.400000"
    last = build["last_run"]
    assert last["id"] == run["id"]
    assert last["status"] == "succeeded"
    assert last["tokens"] == 52_000
    assert last["tries"] == 1
    assert last["started_at"] == run["created_at"]
    assert last["finished_at"] == run["finished_at"]
    created = datetime.fromisoformat(run["created_at"])
    finished = datetime.fromisoformat(run["finished_at"])
    assert last["duration_s"] == int((finished - created).total_seconds())

    plan = _card(client, "plan")
    assert plan["state"] == "idle"
    assert plan["ticket"] is None
    assert plan["cost"] == "0.000000"
    assert plan["last_run"] is None
    assert plan["model"] == "claude-opus-5-5"


def test_ft_12_2_card_counts_tries_and_sums_ticket_cost(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-12.2 card counts tries and sums the ticket cost of the agent (SC-40)."""
    add_cart_project(client, tmp_path)
    assert client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"}).status_code == 200
    assert client.put("/api/prices/claude-haiku-5-5", json={"input": 4, "output": 20}).status_code == 200
    llm.script = [final_with(LlmUsage(40_000, 12_000)), final_with(LlmUsage(40_000, 12_000))]
    start_and_wait(client, "build")
    second = start_and_wait(client, "build")

    build = _card(client, "build")
    assert build["last_run"]["tries"] == 2
    assert build["last_run"]["id"] == second["id"]
    assert build["last_run"]["tokens"] == 52_000
    assert build["cost"] == "0.800000"


def test_ft_12_3_run_start_turns_card_active_live(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-12.3 a run start turns the card active on the event stream (SC-41)."""
    add_cart_project(client, tmp_path)
    llm.responder = blocking_build(settings.skills_dir, 1.0)
    with client.stream("GET", "/api/events") as r:
        lines = r.iter_lines()
        assert next(lines) == ": connected"
        assert r.headers["content-type"].startswith("text/event-stream")

        t0 = monotonic()
        post = client.post(
            "/api/projects/shop/runs", json={"agent": "build", "feature": "cart", "ticket": "TKT-1"}
        )
        assert post.status_code == 202
        run_id = post.json()["id"]

        ev = next_event(lines, "run.started")
        assert ev["type"] == "run.started"
        assert ev["payload"]["agent"] == "build"
        assert ev["payload"]["ticket"] == "TKT-1"
        assert isinstance(ev["project_id"], str) and ev["project_id"]
        assert "at" in ev
        assert monotonic() - t0 < 1.0

        build = _card(client, "build")
        assert build["state"] == "active"
        assert build["ticket"] == "TKT-1"

        wait_run(client, run_id)
        assert next_event(lines, "run.finished")["payload"]["run_id"] == run_id


def test_ft_12_4_open_incident_turns_card_stuck_live(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-12.4 an open incident turns the card stuck on the event stream (SC-42)."""
    add_cart_project(client, tmp_path)
    llm.fail_with = LlmError("overloaded")
    failed = start_and_wait(client, "build")
    assert failed["status"] == "failed"
    llm.fail_with = None

    with client.stream("GET", "/api/events") as r:
        lines = r.iter_lines()
        assert next(lines) == ": connected"

        step = client.post("/api/projects/shop/features/cart/step")
        assert step.status_code == 200
        assert step.json()["reason"] == "resolving"

        ev = next_event(lines, "incident.opened")
        assert ev["payload"]["ticket"] == "TKT-1"
        assert ev["payload"]["trigger"] == "crash"

    build = _card(client, "build")
    assert build["state"] == "stuck"
    assert build["last_run"]["status"] == "failed"
    assert _card(client, "resolver")["state"] in ("active", "idle")


def test_ft_12_5_idle_stream_sends_heartbeat(client: TestClient) -> None:
    """FT-12.5 an idle event stream sends a heartbeat comment."""
    with client.stream("GET", "/api/events") as r:
        lines = r.iter_lines()
        assert next(lines) == ": connected"
        deadline = monotonic() + 2.0
        for line in lines:
            if line == ": ping":
                break
            assert monotonic() < deadline, "no heartbeat within 2 s"
        else:
            raise AssertionError("stream ended without heartbeat")
