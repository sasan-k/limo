from typing import Literal

from pydantic import BaseModel

from limo.agents.models import RunStatus

AgentState = Literal["idle", "active", "stuck"]


class LastRun(BaseModel):
    id: str
    status: RunStatus
    tokens: int
    started_at: str
    finished_at: str | None
    duration_s: int | None
    tries: int


class AgentCard(BaseModel):
    agent: str
    model: str
    state: AgentState
    project: str | None
    feature: str | None
    ticket: str | None
    cost: str
    last_run: LastRun | None
