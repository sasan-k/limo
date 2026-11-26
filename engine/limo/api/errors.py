from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from limo.common.errors import LimoError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LimoError)
    def _limo_error(_: Request, e: LimoError) -> JSONResponse:
        return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})

    @app.exception_handler(RequestValidationError)
    def _validation_error(_: Request, e: RequestValidationError) -> JSONResponse:
        first = e.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        message = f"{location}: {first['msg']}"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": message}},
        )
