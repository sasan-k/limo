import hmac
import secrets
import threading
from dataclasses import dataclass
from typing import Any

from limo.agents.models import ToolCall
from limo.agents.repo import RunRepo
from limo.agents.tools import ToolBox, ToolContext
from limo.common.errors import Unauthorized

PROTOCOL_VERSION = "2025-06-18"
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


@dataclass
class _Session:
    token: str
    ctx: ToolContext
    seq: int = 0


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class McpGateway:
    """Per-run MCP tool server (ADR-14): serves only the run's allowlisted tools behind a run token.
    Every call goes through ToolBox (same limits as the API backend) and is recorded in tool_calls."""

    def __init__(self, tools: ToolBox, runs: RunRepo) -> None:
        self._tools = tools
        self._runs = runs
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def open(self, run_id: str, ctx: ToolContext) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[run_id] = _Session(token, ctx)
        return token

    def close(self, run_id: str) -> None:
        with self._lock:
            self._sessions.pop(run_id, None)

    def handle(self, run_id: str, token: str | None, message: dict[str, Any]) -> dict[str, Any] | None:
        """One JSON-RPC message; None for notifications (no `id`)."""
        session = self._session(run_id, token)
        if "id" not in message:
            return None
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            reply["result"] = self._dispatch(run_id, session, message.get("method"), message.get("params"))
        except _RpcError as e:
            reply["error"] = {"code": e.code, "message": e.message}
        return reply

    def _session(self, run_id: str, token: str | None) -> _Session:
        with self._lock:
            session = self._sessions.get(run_id)
        if session is None or token is None or not hmac.compare_digest(session.token, token):
            raise Unauthorized("mcp_unauthorized", "unknown run or bad token")
        return session

    def _dispatch(self, run_id: str, session: _Session, method: object, params: object) -> dict[str, Any]:
        args = params if isinstance(params, dict) else {}
        if method == "initialize":
            return {
                "protocolVersion": args.get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "limo", "version": "1"},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            specs = self._tools.specs(session.ctx.agent)
            return {
                "tools": [
                    {"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"]}
                    for s in specs
                ]
            }
        if method == "tools/call":
            return self._call(run_id, session, args)
        raise _RpcError(METHOD_NOT_FOUND, f"method not found: {method}")

    def _call(self, run_id: str, session: _Session, args: dict[str, Any]) -> dict[str, Any]:
        name = args.get("name")
        arguments = args.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise _RpcError(INVALID_PARAMS, "tools/call needs a name and an arguments object")
        outcome = self._tools.call(session.ctx, name, arguments)
        with self._lock:
            session.seq += 1
            seq = session.seq
        call = ToolCall(
            seq=seq, name=name, target=outcome.target, status=outcome.status, summary=outcome.text[:200]
        )
        self._runs.add_tool_call(run_id, call)
        return {"content": [{"type": "text", "text": outcome.text}], "isError": outcome.status != "ok"}
