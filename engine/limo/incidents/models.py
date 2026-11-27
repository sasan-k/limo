from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

IncidentStatus = Literal["open", "resolved", "needs_human"]


class Incident(BaseModel):
    ticket: str
    k: int
    trigger: str
    status: IncidentStatus
    action: str | None
    run_id: str | None


@dataclass(frozen=True)
class IncidentRow:
    id: str
    ticket: str
    k: int
    trigger: str
    status: IncidentStatus
    run_id: str | None
    resolver_run_id: str | None
    action: str | None
    note_pending: bool = False
