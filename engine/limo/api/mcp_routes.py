from typing import Annotated, Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response

from limo.agents.mcp import McpGateway


def mcp_router(gateway: McpGateway) -> APIRouter:
    """Per-run MCP endpoint for `claude -p` agents (ADR-14); not part of the UI API."""
    router = APIRouter(include_in_schema=False)

    @router.post("/mcp/runs/{run_id}", response_model=None)
    def mcp_message(
        run_id: str, message: dict[str, Any], authorization: Annotated[str | None, Header()] = None
    ) -> Response:
        token = authorization.removeprefix("Bearer ") if authorization else None
        reply = gateway.handle(run_id, token, message)
        return Response(status_code=202) if reply is None else JSONResponse(reply)

    return router
