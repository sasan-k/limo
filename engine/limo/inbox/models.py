from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Hold(BaseModel):
    id: str
    project: str
    feature: str
    ticket: str
    kind: Literal["budget"]
    reason: str
    created_at: str


class InboxItem(BaseModel):
    id: str
    project: str
    feature: str
    ticket: str
    kind: Literal["budget", "escalation"]
    reason: str
    created_at: str
    link: str | None = None


class ContinueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str | None = Field(default=None, min_length=1, max_length=2000)
