import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from limo.agents.mcp import McpGateway
from limo.agents.models import Run
from limo.agents.tools import ToolContext
from limo.llm.ports import AgentCli, CliRequest, CliResult


@dataclass(frozen=True)
class CliConfig:
    engine_url: str
    cwd: Path
    config_dir: Path
    timeout_s: float


class CliRunner:
    """Runs one agent as a local `claude -p` session whose only tools are this run's MCP tools (ADR-14)."""

    def __init__(self, cli: AgentCli, gateway: McpGateway, config: CliConfig) -> None:
        self._cli = cli
        self._gateway = gateway
        self._config = config

    def run(
        self,
        run: Run,
        ctx: ToolContext,
        task: str,
        budget_usd: float | None,
        on_event: Callable[[dict[str, Any]], None],
    ) -> CliResult:
        token = self._gateway.open(run.id, ctx)
        config_file = self._config.config_dir / f"{run.id}.json"
        try:
            self._write_mcp_config(config_file, run.id, token)
            request = CliRequest(
                model=run.model,
                task=task,
                system_prompt_file=ctx.agent_dir / "SKILL.md",
                mcp_config_file=config_file,
                cwd=self._config.cwd,
                timeout_s=self._config.timeout_s,
                max_budget_usd=budget_usd,
            )
            return self._cli.run(request, on_event)
        finally:
            self._gateway.close(run.id)
            config_file.unlink(missing_ok=True)

    def _write_mcp_config(self, path: Path, run_id: str, token: str) -> None:
        """Owner-only file: it holds the run token."""
        path.parent.mkdir(parents=True, exist_ok=True)
        server = {
            "type": "http",
            "url": f"{self._config.engine_url}/mcp/runs/{run_id}",
            "headers": {"Authorization": f"Bearer {token}"},
        }
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"mcpServers": {"limo": server}}, f)
