from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentName = Literal["architecture", "spec", "plan", "build", "verify", "close", "resolver"]


class DefaultsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: float = Field(gt=0, le=10000)
    agent: float = Field(gt=0, le=10000)


class Defaults(BaseModel):
    ticket: str
    agent: str


class BudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0, le=10000)
    agent: AgentName | None = None


class Line(BaseModel):
    budget: str
    spent: str


class TicketBudget(BaseModel):
    ticket: Line
    agents: dict[str, Line]
