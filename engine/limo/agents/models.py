from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Agent(BaseModel):
    name: str
    prompt: str
    references: list[str]
    model: str | None = None


class ModelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: Literal["architecture", "spec", "plan", "build", "verify", "close", "resolver"]
    feature: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    ticket: str | None = Field(default=None, pattern=r"^TKT-\d+$")


class Run(BaseModel):
    id: str
    project: str
    agent: str
    feature: str
    ticket: str | None
    status: Literal["queued", "running", "succeeded", "failed"]
    model: str
    output: str | None
    error: str | None
    created_at: str
    finished_at: str | None


class ToolCall(BaseModel):
    seq: int
    name: str
    target: str
    status: Literal["ok", "error", "rejected"]
    summary: str
