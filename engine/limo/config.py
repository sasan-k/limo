from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIMO_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / ".factory"
    skills_dir: Path = REPO_ROOT / "skills"
    command_timeout_s: float = 600.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def workspaces_dir(self) -> Path:
        return self.data_dir / "workspaces"
