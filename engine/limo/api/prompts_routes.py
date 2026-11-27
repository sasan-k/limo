from typing import Annotated

from fastapi import APIRouter, Query

from limo.prompts.models import PATH_PATTERN, PromptFile, PromptSaveIn, PromptVersion, RollbackIn
from limo.prompts.service import PromptService

FilePath = Annotated[str, Query(pattern=PATH_PATTERN, max_length=200)]


def prompts_router(service: PromptService) -> APIRouter:
    router = APIRouter(prefix="/api/agents/{name}")

    @router.get("/files", response_model=list[str])
    def list_files(name: str) -> list[str]:
        return service.files(name)

    @router.get("/file", response_model=PromptFile)
    def read_file(name: str, path: FilePath) -> PromptFile:
        return service.read(name, path)

    @router.put("/file", response_model=PromptFile)
    def save_file(name: str, path: FilePath, body: PromptSaveIn) -> PromptFile:
        return service.save(name, path, body)

    @router.get("/history", response_model=list[PromptVersion])
    def file_history(name: str, path: FilePath) -> list[PromptVersion]:
        return service.history(name, path)

    @router.post("/rollback", response_model=PromptFile)
    def rollback_file(name: str, path: FilePath, body: RollbackIn) -> PromptFile:
        return service.rollback(name, path, body.version)

    return router
