---
ticket: TKT-2
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-2

## Results
- functional (ticket): 14/14 FT functions
- full suite: 28/28 (`mise run test`)
- gates: lint ✅ · duplication ✅ · architecture ✅ · types ✅ (lint passes only via 2 `noqa`)
- trace check: ok
- review: 2 findings

## Failures & findings
### R-1 parameter limit suppressed with noqa
- class: plan
- rule: code-rules.md › Size & complexity (params ≤ 5)
- where: engine/limo/agents/service.py:17 (8 params), engine/limo/agents/repo.py:77 (6 params)
- why: the plan specified these signatures; `# noqa: PLR0913` hides a code-rules violation
- error:
```
def __init__(  # noqa: PLR0913
def add_tool_call(  # noqa: PLR0913
```
- fix hint: group `skills_dir, model, max_turns` into a `RunConfig` dataclass; pass a `ToolCall` to `add_tool_call`; remove both noqa

### R-2 one query per tool call to compute seq
- class: build
- rule: performance.md › Data access (no N+1)
- where: engine/limo/agents/service.py:116
- why: `len(self._runs.tool_calls(run.id)) + 1` reloads all tool calls for every call; plan said "running count"
- error:
```
seq = len(self._runs.tool_calls(run.id)) + 1
```
- fix hint: keep a counter in `_loop` and pass it to `_tool_result`
