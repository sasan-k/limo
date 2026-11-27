import tempfile
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIMO_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / ".factory"
    skills_dir: Path = REPO_ROOT / "skills"
    scripts_dir: Path = REPO_ROOT / "scripts"
    command_timeout_s: float = 600.0
    run_timeout_s: float = 1800.0
    max_concurrent_tickets: int = 1
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key")
    )
    default_model: str = "claude-opus-5-5"
    agent_models: dict[str, str] = {
        "spec": "claude-sonnet-5-5",
        "build": "claude-haiku-5-5",
        "verify": "claude-sonnet-5-5",
        "close": "claude-sonnet-5-5",
    }
    max_turns: int = 50
    default_ticket_budget: float = 10.0
    default_agent_budget: float = 5.0
    github_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GITHUB_TOKEN", "github_token")
    )
    gitlab_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GITLAB_TOKEN", "gitlab_token")
    )
    github_api_url: str = "https://api.github.com"
    gitlab_api_url: str = "https://gitlab.com/api/v4"
    host_timeout_s: float = 10.0
    sse_heartbeat_s: float = 15.0
    runner_tick_s: float = 2.0
    host_poll_s: float = 180.0
    agent_backend: Literal["claude-cli", "api"] = "claude-cli"
    claude_bin: str = "claude"
    engine_url: str = "http://127.0.0.1:8700"
    agent_cwd: Path = Path(tempfile.gettempdir()) / "limo-agent"

    def model_for(self, agent: str) -> str:
        """Default model of an agent unless set from the UI/API: `agent_models`, else `default_model`."""
        return self.agent_models.get(agent, self.default_model)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"
