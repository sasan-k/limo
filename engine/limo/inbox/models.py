from typing import Literal

from pydantic import BaseModel


class Hold(BaseModel):
    id: str
    project: str
    feature: str
    ticket: str
    kind: Literal["budget"]
    reason: str
    created_at: str
