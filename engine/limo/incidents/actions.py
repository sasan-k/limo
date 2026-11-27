import json
import re
from typing import Any

ALLOWED = {"retry", "answer", "edit-ticket", "replan", "escalate"}
RETRY_STATUS = {"plan": "todo", "build": "planned", "verify": "built", "close": "verified"}
# ```json {...}``` as in the resolve-report template, or an ```action block of `key: value` lines
ACTION_BLOCK = re.compile(r"```(json|action)[ \t]*\n?(.*?)```", re.S)
KEY_LINE = re.compile(r"^([a-z][a-z_-]*):[ \t]*(.*)$")


def _key_values(text: str) -> dict[str, Any] | None:
    """`key: value` lines; `key: |` takes the following indented lines as one multi-line value."""
    result: dict[str, Any] = {}
    key: str | None = None
    block: list[str] | None = None
    for line in text.splitlines():
        if block is not None and (line.startswith((" ", "\t")) or not line.strip()):
            block.append(line.strip())
            continue
        block = None
        match = KEY_LINE.match(line)
        if match is None:
            if line.strip():
                return None
            continue
        key, value = match.groups()
        if value.strip() == "|":
            block = []
            result[key] = block
        else:
            result[key] = value.strip()
    values = {k: "\n".join(v).strip() if isinstance(v, list) else v for k, v in result.items()}
    if "action" in values and "type" not in values:
        values["type"] = values.pop("action")
    return values


def _decode(kind: str, body: str) -> Any:
    text = body.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return _key_values(text) if kind == "action" else None


def parse_action(output: str | None) -> dict[str, Any] | None:
    if not output:
        return None
    blocks = ACTION_BLOCK.findall(output)
    if not blocks:
        return None
    action = _decode(*blocks[-1])
    if not isinstance(action, dict) or action.get("type") not in ALLOWED:
        return None
    return action
