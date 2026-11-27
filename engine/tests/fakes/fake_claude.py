#!/usr/bin/env python3
"""Stand-in for the `claude` binary in adapter tests: writes its argv and env names to ./seen.json
(it runs in the request's cwd), then acts on the task given after `-p`:
`ok` → stream-json events ending in a success result; `error` → error result; `crash` → exit 1 with
stderr; `sleep` → sleeps 30 s (timeout test)."""

import json
import os
import sys
import time

argv = sys.argv[1:]
with open("seen.json", "w") as f:
    json.dump({"argv": argv, "env": sorted(os.environ)}, f)
task = argv[argv.index("-p") + 1]
if task == "crash":
    print("Not logged in. Run claude /login", file=sys.stderr)
    sys.exit(1)
if task == "sleep":
    time.sleep(30)
print("not json")
print(json.dumps({"type": "system", "subtype": "init", "tools": ["mcp__limo__read_file"]}))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}))
usage = {
    "input_tokens": 12,
    "output_tokens": 34,
    "cache_read_input_tokens": 56,
    "cache_creation_input_tokens": 78,
}
subtype, is_error = ("success", False) if task == "ok" else ("error_max_budget_usd", True)
result = {"type": "result", "subtype": subtype, "is_error": is_error, "result": "all done"}
print(json.dumps({**result, "total_cost_usd": 0.0421, "usage": usage}))
