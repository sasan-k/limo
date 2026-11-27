from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeatureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    requirements: str = Field(min_length=1, max_length=200_000)


class Feature(BaseModel):
    name: str
    phase: Literal["architecture", "spec", "nfr", "tickets"]
    created_at: str
