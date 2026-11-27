from pydantic import BaseModel, ConfigDict, Field

PATH_PATTERN = r"^(SKILL\.md|templates(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+)$"
SHA_PATTERN = r"^[0-9a-f]{40}$"
MAX_CONTENT = 262_144


class PromptFile(BaseModel):
    agent: str
    path: str
    content: str
    version: str | None


class PromptVersion(BaseModel):
    version: str
    saved_at: str
    message: str


class PromptSaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(max_length=MAX_CONTENT)
    base_version: str | None = Field(default=None, pattern=SHA_PATTERN)


class RollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=SHA_PATTERN)
