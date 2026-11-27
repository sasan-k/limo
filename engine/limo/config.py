from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIMO_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / ".factory"
    skills_dir: Path = REPO_ROOT / "skills"
    scripts_dir: Path = REPO_ROOT / "scripts"
    command_timeout_s: float = 600.0
    max_concurrent_tickets: int = 1
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key")
    )
    default_model: str = "claude-opus-5-5"
    max_turns: int = 50
    default_ticket_budget: float = 10.0
    default_agent_budget: float = 5.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"
