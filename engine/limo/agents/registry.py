from pathlib import Path

from limo.agents.models import Agent
from limo.common.constants import AGENT_NAMES


class AgentRegistry:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def list(self) -> list[Agent]:
        root = self._skills_dir.parent
        agents: list[Agent] = []
        for name in AGENT_NAMES:
            d = self._skills_dir / name
            templates = d / "templates"
            references = (
                sorted(p.relative_to(root).as_posix() for p in templates.rglob("*") if p.is_file())
                if templates.is_dir()
                else []
            )
            agents.append(
                Agent(
                    name=name,
                    prompt=(d / "SKILL.md").relative_to(root).as_posix(),
                    references=references,
                )
            )
        return agents
