from pydantic import BaseModel


class BoardTicket(BaseModel):
    id: str
    title: str
    status: str
    depends_on: list[str]
    build_tries: int
    plan_tries: int


class BoardFeature(BaseModel):
    name: str
    tickets: list[BoardTicket]


class Board(BaseModel):
    project: str
    statuses: list[str]
    features: list[BoardFeature]
