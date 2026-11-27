from fastapi import APIRouter

from limo.board.models import Board
from limo.board.service import BoardService


def board_router(service: BoardService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/projects/{name}/board", response_model=Board)
    def get_board(name: str) -> Board:
        return service.board(name)

    return router
