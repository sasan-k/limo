from pydantic import BaseModel, ConfigDict, Field


class PriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: float = Field(ge=0, le=1000)
    output: float = Field(ge=0, le=1000)
    cache_read: float = Field(default=0, ge=0, le=1000)
    cache_write: float = Field(default=0, ge=0, le=1000)


class Price(BaseModel):
    model: str
    input: str
    output: str
    cache_read: str
    cache_write: str


class TokenCounts(BaseModel):
    input: int
    output: int
    cache_read: int
    cache_write: int


class AgentTicketCost(BaseModel):
    agent: str
    ticket: str
    cost: str


class CostTotals(BaseModel):
    per_agent: dict[str, str]
    per_ticket: dict[str, str]
    per_agent_ticket: list[AgentTicketCost]
    overall: str
