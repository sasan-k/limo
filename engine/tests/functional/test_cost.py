from pathlib import Path

from fastapi.testclient import TestClient

from limo.llm.ports import LlmUsage
from tests.builders import add_cart_project, start_and_wait
from tests.fakes.llm import FakeLlm, final_with, tool_use

OPUS_PATH = "/api/prices/claude-opus-5-5"
OPUS_PRICE = {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 5}


def test_ft_4_1_run_records_token_totals(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-4.1 run tokens are summed across all Claude API calls of the run."""
    add_cart_project(client, tmp_path)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    llm.script = [
        tool_use("list_files", {"path": "."}, usage=LlmUsage(10_000, 2_000, 0, 8_000)),
        final_with(LlmUsage(3_000, 1_000, 8_000, 0)),
    ]
    run = start_and_wait(client, "plan")
    assert run["model"] == "claude-opus-5-5"
    assert run["tokens"] == {"input": 13_000, "output": 3_000, "cache_read": 8_000, "cache_write": 8_000}


def test_ft_4_2_run_cost_at_million_token_boundary(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-4.2 a run's cost is computed from its usage and the opus price."""
    add_cart_project(client, tmp_path)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    llm.script = [final_with(LlmUsage(1_000_000, 100_000))]
    run = start_and_wait(client, "plan")
    assert run["cost"] == "6.000000"


def test_ft_4_3_build_run_uses_configured_model_price(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-4.3 a build run is priced with the price of its configured model."""
    add_cart_project(client, tmp_path)
    assert client.put("/api/agents/build/model", json={"model": "claude-haiku-5-5"}).status_code == 200
    r = client.put("/api/prices/claude-haiku-5-5", json={"input": 0.10, "output": 0.50})
    assert r.status_code == 200
    assert r.json()["input"] == "0.100000"
    llm.script = [final_with(LlmUsage(2_000_000, 200_000))]
    run = start_and_wait(client, "build")
    assert run["cost"] == "0.300000"


def test_ft_4_4_stored_cost_ignores_later_price_change(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-4.4 changing a price does not change the cost of an earlier run."""
    add_cart_project(client, tmp_path)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    llm.script = [final_with(LlmUsage(1_000_000, 100_000))]
    run = start_and_wait(client, "plan")
    client.put(OPUS_PATH, json={"input": 8, "output": 40})
    assert client.get(f"/api/runs/{run['id']}").json()["cost"] == "6.000000"


def test_ft_4_5_project_cost_totals(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-4.5 project totals group cost by agent, ticket and agent and ticket."""
    add_cart_project(client, tmp_path)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    llm.script = [final_with(LlmUsage(250_000, 0))]
    start_and_wait(client, "plan", "TKT-1")
    llm.script = [final_with(LlmUsage(50_000, 0))]
    start_and_wait(client, "build", "TKT-1")
    llm.script = [final_with(LlmUsage(75_000, 0))]
    start_and_wait(client, "build", "TKT-1")
    llm.script = [final_with(LlmUsage(500_000, 0))]
    start_and_wait(client, "plan", "TKT-2")
    body = client.get("/api/projects/shop/costs").json()
    assert body["per_agent"] == {"build": "0.500000", "plan": "3.000000"}
    assert body["per_ticket"] == {"TKT-1": "1.500000", "TKT-2": "2.000000"}
    assert {"agent": "build", "ticket": "TKT-1", "cost": "0.500000"} in body["per_agent_ticket"]
    assert body["overall"] == "3.500000"


def test_ft_4_6_invalid_price_is_rejected(client: TestClient) -> None:
    """FT-4.6 invalid price bodies and model names return 422 validation_error."""
    bodies = [{"input": -1, "output": 1}, {"output": 1}, {"input": 1, "output": 1, "currency": "EUR"}]
    for body in bodies:
        r = client.put(OPUS_PATH, json=body)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
    r = client.put("/api/prices/Bad Model!", json={"input": 1, "output": 1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_ft_4_7_price_upsert_and_list(client: TestClient) -> None:
    """FT-4.7 setting a price twice keeps one entry holding the latest values."""
    client.put(OPUS_PATH, json=OPUS_PRICE)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    client.put(OPUS_PATH, json={"input": 5, "output": 25})
    prices = [p for p in client.get("/api/prices").json() if p["model"] == "claude-opus-5-5"]
    assert len(prices) == 1
    assert prices[0]["input"] == "5.000000"
    assert prices[0]["output"] == "25.000000"
    assert prices[0]["cache_read"] == "0.000000"


def test_ft_4_8_price_bounds(client: TestClient) -> None:
    """FT-4.8 price amounts accept 0 and 1000 and reject values above 1000."""
    assert client.put(OPUS_PATH, json={"input": 0, "output": 1000}).status_code == 200
    assert client.put(OPUS_PATH, json={"input": 1000.01, "output": 1}).status_code == 422


def test_ft_4_9_costs_of_unknown_project(client: TestClient) -> None:
    """FT-4.9 cost totals of an unknown project return 404 project_not_found."""
    r = client.get("/api/projects/nope/costs")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_ft_4_10_costs_of_project_without_runs(client: TestClient, tmp_path: Path) -> None:
    """FT-4.10 a project without runs has empty totals."""
    add_cart_project(client, tmp_path)
    assert client.get("/api/projects/shop/costs").json() == {
        "per_agent": {},
        "per_ticket": {},
        "per_agent_ticket": [],
        "overall": "0.000000",
    }


def test_ft_4_11_unpriced_model_costs_zero(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-4.11 a model without a price records tokens and zero cost."""
    add_cart_project(client, tmp_path)
    llm.script = [final_with(LlmUsage(1_000, 1_000))]
    run = start_and_wait(client, "plan")
    assert run["tokens"]["input"] == 1_000
    assert run["cost"] == "0.000000"


def test_ft_4_12_no_prices(client: TestClient) -> None:
    """FT-4.12 a fresh app lists no prices."""
    assert client.get("/api/prices").json() == []
