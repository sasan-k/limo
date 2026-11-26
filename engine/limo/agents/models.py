from pydantic import BaseModel


class Agent(BaseModel):
    name: str
    prompt: str
    references: list[str]
