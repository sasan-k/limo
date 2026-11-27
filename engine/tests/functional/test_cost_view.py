from pathlib import Path

from fastapi.testclient import TestClient

from limo.llm.ports import LlmUsage
from tests.builders import add_cart_project, start_and_wait
from tests.fakes.llm import FakeLlm, final_with

OPUS_PATH = "/api/prices/claude-opus-5-5"
OPUS_PRICE = {"input": 4, "output": 20}


def test_ft_15_5_cost_totals_match_the_scenario(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-15.5 cost totals match the scenario: per agent, per ticket, per agent on ticket and overall."""
    add_cart_project(client, tmp_path)
    client.put(OPUS_PATH, json=OPUS_PRICE)
    llm.script = [final_with(LlmUsage(250_000, 0))]
    start_and_wait(client, "plan")
    llm.script = [final_with(LlmUsage(125_000, 0))]
    start_and_wait(client, "build")
    costs = client.get("/api/projects/shop/costs").json()
    assert costs["per_agent"] == {"build": "0.500000", "plan": "1.000000"}
    assert costs["per_ticket"] == {"TKT-1": "1.500000"}
    assert {"agent": "build", "ticket": "TKT-1", "cost": "0.500000"} in costs["per_agent_ticket"]
    assert costs["overall"] == "1.500000"
