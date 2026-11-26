from pathlib import Path

from fastapi.testclient import TestClient

from limo.app import create_app
from limo.common.constants import AGENT_NAMES
from limo.config import Settings


def test_ft_1_9_seven_agents_from_real_skills(client: TestClient) -> None:
    """FT-1.9 the real skills directory yields the seven agents, with plan prompt and template reference."""
    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()
    assert [a["name"] for a in agents] == [
        "architecture",
        "spec",
        "plan",
        "build",
        "verify",
        "close",
        "resolver",
    ]
    plan = next(a for a in agents if a["name"] == "plan")
    assert plan["prompt"] == "skills/plan/SKILL.md"
    assert "skills/plan/templates/plan.md" in plan["references"]


def test_ft_1_10_agents_without_templates(tmp_path: Path) -> None:
    """FT-1.10 agents with only SKILL.md have no references."""
    for name in AGENT_NAMES:
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n")
    settings = Settings(data_dir=tmp_path / "data", skills_dir=tmp_path / "skills", _env_file=None)
    with TestClient(create_app(settings)) as client:
        agents = client.get("/api/agents").json()
    assert len(agents) == 7
    assert all(a["references"] == [] for a in agents)
