from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from limo.cost.models import TokenCounts


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
    args: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9 =-]{0,79}$")
    ticket_status: str | None = Field(default=None, pattern=r"^[a-z]+$")
    note: str | None = Field(default=None, max_length=500)


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
    tokens: TokenCounts | None = None
    cost: str | None = None
    args: str | None = None
    ticket_status: str | None = None
    note: str | None = None


class ToolCall(BaseModel):
    seq: int
    name: str
    target: str
    status: Literal["ok", "error", "rejected"]
    summary: str
