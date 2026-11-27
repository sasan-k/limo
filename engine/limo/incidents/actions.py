import json
import re
from typing import Any

ALLOWED = {"retry", "answer", "edit-ticket", "replan", "escalate"}
RETRY_STATUS = {"plan": "todo", "build": "planned", "verify": "built", "close": "verified"}
ACTION_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def parse_action(output: str | None) -> dict[str, Any] | None:
    if not output:
        return None
    blocks = ACTION_BLOCK.findall(output)
    if not blocks:
        return None
    try:
        action = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(action, dict) or action.get("type") not in ALLOWED:
        return None
    return action
