---
ticket: TKT-<n>
incident: <k>
trigger: <blocked | no-transition | crash | timeout | limits | question>
diagnosis: <transient | no-transition | answerable | underspecified | plan-detail | other>
confidence: <high | low>
---
# Resolve report TKT-<n> #<k>

## Evidence
<!-- One item per claim: source + ≤ 5 quoted lines. -->
- `<file:line | CI job URL | issue comment URL>` — <what it shows>

## Reasoning
<!-- ≤ 3 lines: why this diagnosis and not another. -->

## Action
<!-- Exactly one JSON object. The runner validates it against the allowlist and applies it. -->
```json
{"type": "retry", "stage": "<plan|build|verify|close>"}
```
<!-- or {"type": "answer", "question": "Q-<n>", "answer": "<one line>", "source": "<evidence>"}
     or {"type": "edit-ticket", "title": "<one line>", "source": "<evidence>"}
     or {"type": "replan", "fix": "<exact plan correction, ≤ 3 lines>", "source": "<evidence>"}
     or {"type": "escalate", "summary": "<≤ 3 lines>", "ask": "<one question for a human>"} -->
