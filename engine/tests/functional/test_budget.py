from pathlib import Path

from fastapi.testclient import TestClient

from limo.common.constants import AGENT_NAMES
from limo.config import Settings
from limo.llm.ports import LlmUsage
from tests.builders import add_cart_project, set_status, start_and_wait
from tests.fakes.llm import FakeLlm, final_with, tool_use

B = "/api/projects/shop/features/cart/tickets/TKT-1/budget"
RUNNER = "/api/projects/shop/features/cart/step"


def _price(client: TestClient) -> None:
    r = client.put("/api/prices/claude-opus-5-5", json={"input": 4, "output": 20})
    assert r.status_code == 200


def _setup(client: TestClient, tmp_path: Path, defaults: dict[str, float]) -> None:
    add_cart_project(client, tmp_path)
    _price(client)
    r = client.put("/api/budgets/defaults", json=defaults)
    assert r.status_code == 200


def _reach_ticket_budget(client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path) -> str:
    """Defaults ticket 5 / agent 100; plan costs 4.90, then a build call costs 1.00 (ticket 5.90).

    Returns the hold id.
    """
    _setup(client, tmp_path, {"ticket": 5, "agent": 100})
    llm.script = [final_with(LlmUsage(input_tokens=1_225_000))]
    assert start_and_wait(client, "plan")["status"] == "succeeded"
    llm.script = [tool_use("read_file", {"path": "src/cart.py"}, usage=LlmUsage(output_tokens=50_000))]
    before = len(llm.requests)
    run = start_and_wait(client, "build")
    assert run["status"] == "failed"
    assert run["error"].startswith("budget:")
    assert len(llm.requests) - before == 1
    holds = client.get("/api/inbox").json()
    assert len(holds) == 1
    return holds[0]["id"]


def test_ft_17_1_defaults_and_ticket_budget_read(client: TestClient, tmp_path: Path) -> None:
    """FT-17.1 defaults set and read back; ticket budget shows defaults and zero spend."""
    add_cart_project(client, tmp_path)
    r = client.put("/api/budgets/defaults", json={"ticket": 5, "agent": 2})
    assert r.status_code == 200
    assert r.json() == {"ticket": "5.000000", "agent": "2.000000"}
    body = client.get(B).json()
    assert body["ticket"]["budget"] == "5.000000"
    assert body["agents"]["build"]["budget"] == "2.000000"
    assert body["ticket"]["spent"] == "0.000000"


def test_ft_17_2_ticket_budget_stops_run_and_opens_hold(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-17.2 reaching the ticket budget fails the run after one call and opens a budget hold."""
    _reach_ticket_budget(client, llm, settings, tmp_path)
    resolver = (settings.skills_dir / "resolver" / "SKILL.md").read_text()
    assert all(r.system != resolver for r in llm.requests)
    holds = client.get("/api/inbox").json()
    assert len(holds) == 1
    assert holds[0]["project"] == "shop"
    assert holds[0]["feature"] == "cart"
    assert holds[0]["ticket"] == "TKT-1"
    assert holds[0]["kind"] == "budget"
    assert holds[0]["reason"] == "ticket budget reached: $5.90 of $5.00"


def test_ft_17_3_agent_budget_stops_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-17.3 reaching a build agent budget on the ticket fails the next build run after one call."""
    _setup(client, tmp_path, {"ticket": 100, "agent": 2})
    llm.script = [final_with(LlmUsage(input_tokens=487_500))]
    assert start_and_wait(client, "build")["status"] == "succeeded"
    llm.script = [tool_use("read_file", {"path": "src/cart.py"}, usage=LlmUsage(output_tokens=5_000))]
    before = len(llm.requests)
    run = start_and_wait(client, "build")
    assert run["status"] == "failed"
    assert len(llm.requests) - before == 1
    holds = client.get("/api/inbox").json()
    assert len(holds) == 1
    assert holds[0]["reason"] == "build budget reached: $2.05 of $2.00"


def test_ft_17_4_raised_budget_and_continue_runs_one_step(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-17.4 raising the ticket budget and continuing the hold clears it and starts the next step."""
    hold_id = _reach_ticket_budget(client, llm, settings, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    r = client.put(B, json={"amount": 8, "agent": None})
    assert r.status_code == 200
    assert r.json()["ticket"]["budget"] == "8.000000"
    r = client.post(f"/api/inbox/{hold_id}/continue")
    assert r.status_code == 200
    body = r.json()
    assert body["reason"] == "started"
    assert body["run"]["agent"] == "build"
    assert body["run"]["ticket"] == "TKT-1"
    assert client.get("/api/inbox").json() == []


def test_ft_17_5_runner_skips_held_ticket(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-17.5 the runner does not start a held ticket, and its dependent waits."""
    _reach_ticket_budget(client, llm, settings, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    set_status(settings, "shop", "TKT-3", "done")
    r = client.post(RUNNER)
    assert r.json() == {"run": None, "reason": "no_ready_ticket"}


def test_ft_17_6_defaults_reject_invalid_bodies(client: TestClient) -> None:
    """FT-17.6 defaults validation: zero amount, missing field and unknown field are 422."""
    for body in ({"ticket": 0, "agent": 1}, {"ticket": 1}, {"ticket": 1, "agent": 1, "x": 1}):
        assert client.put("/api/budgets/defaults", json=body).status_code == 422


def test_ft_17_7_puts_are_idempotent(client: TestClient, tmp_path: Path) -> None:
    """FT-17.7 repeating the same defaults and override PUT gives the same bodies."""
    add_cart_project(client, tmp_path)
    for _ in range(2):
        r = client.put("/api/budgets/defaults", json={"ticket": 3, "agent": 1})
        assert r.status_code == 200
        assert r.json() == {"ticket": "3.000000", "agent": "1.000000"}
    bodies = []
    for _ in range(2):
        r = client.put(B, json={"amount": 4, "agent": "build"})
        assert r.status_code == 200
        bodies.append(r.json())
    assert bodies[0] == bodies[1]
    status = client.get(B).json()
    assert status["agents"]["build"]["budget"] == "4.000000"
    assert status["ticket"]["budget"] == "3.000000"


def test_ft_17_8_amount_boundaries(client: TestClient, tmp_path: Path) -> None:
    """FT-17.8 amounts at the bounds 0.01 and 10000 are accepted, just above 10000 is rejected."""
    add_cart_project(client, tmp_path)
    assert client.put("/api/budgets/defaults", json={"ticket": 10000, "agent": 0.01}).status_code == 200
    assert client.put("/api/budgets/defaults", json={"ticket": 10000.01, "agent": 1}).status_code == 422
    assert client.put(B, json={"amount": 0.01, "agent": None}).status_code == 200


def test_ft_17_9_override_validation(client: TestClient, tmp_path: Path) -> None:
    """FT-17.9 override validation: unknown agent, bad ticket id and negative amount are 422."""
    add_cart_project(client, tmp_path)
    assert client.put(B, json={"amount": 1, "agent": "deploy"}).status_code == 422
    url = "/api/projects/shop/features/cart/tickets/T1/budget"
    assert client.put(url, json={"amount": 1, "agent": None}).status_code == 422
    assert client.put(B, json={"amount": -1, "agent": None}).status_code == 422


def test_ft_17_10_unknown_project_is_404(client: TestClient) -> None:
    """FT-17.10 GET and PUT on an unknown project return 404 project_not_found."""
    url = "/api/projects/nope/features/cart/tickets/TKT-1/budget"
    for r in (client.get(url), client.put(url, json={"amount": 1, "agent": None})):
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "project_not_found"


def test_ft_17_11_empty_budget_view_and_inbox(client: TestClient, tmp_path: Path) -> None:
    """FT-17.11 with no runs every agent is listed at zero spend and the inbox is empty."""
    add_cart_project(client, tmp_path)
    body = client.get(B).json()
    assert set(body["agents"]) == set(AGENT_NAMES)
    assert all(a["spent"] == "0.000000" for a in body["agents"].values())
    assert client.get("/api/inbox").json() == []


def test_ft_17_12_stops_when_spend_reaches_budget(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-17.12 spend exactly equal to the ticket budget counts as reached."""
    _setup(client, tmp_path, {"ticket": 1, "agent": 100})
    for input_tokens in (247_500, 750):
        llm.script = [final_with(LlmUsage(input_tokens=input_tokens))]
        assert start_and_wait(client, "plan")["status"] == "succeeded"
        assert client.get("/api/inbox").json() == []
    llm.script = [final_with(LlmUsage(input_tokens=1_750))]
    run = start_and_wait(client, "plan")
    assert run["status"] == "failed"
    assert run["error"].startswith("budget:")
    holds = client.get("/api/inbox").json()
    assert len(holds) == 1
    assert holds[0]["reason"] == "ticket budget reached: $1.00 of $1.00"


def test_ft_17_13_continue_not_found_and_twice(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-17.13 continue on an unknown hold is 404; continuing the same hold twice is 409 hold_cleared."""
    hold_id = _reach_ticket_budget(client, llm, settings, tmp_path)
    r = client.post("/api/inbox/nope/continue")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "hold_not_found"
    assert client.post(f"/api/inbox/{hold_id}/continue").status_code == 200
    r = client.post(f"/api/inbox/{hold_id}/continue")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "hold_cleared"
