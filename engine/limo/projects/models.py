from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    git_url: str = Field(min_length=1, max_length=500, pattern=r"^(https://|ssh://|git@|file://)\S+$")
    host: Literal["github", "gitlab"]


class Project(BaseModel):
    id: str
    name: str
    git_url: str
    host: Literal["github", "gitlab"]
    status: Literal["ready"]
    default_branch: str
    workspace: str
    created_at: str
