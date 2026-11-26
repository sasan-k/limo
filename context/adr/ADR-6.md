# ADR-6: Self-hosted agent loop on the Messages API with isolated context and enforced tool allowlists
status: accepted
scope: agents
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
The engine runs each agent's loop with the anthropic SDK (Messages API, streaming). Context = the agent's prompt + task + its allowlisted tools only; reference files are read on demand through a tool.

## Why
DESIGN.md: standalone app, no outside context, local test runs, and role limits enforced by code, not by prompt.

## Rules
- MUST build the request only from `skills/<agent>/` files, the task, and tool results
- MUST reject tool calls not in the agent's allowlist; Build reads only its context pack
- MUST record usage (all token kinds) for every API call
- MUST NOT pass secrets to the model or read `~/.claude`, CLAUDE.md, or user memory

<!-- ===== L3 ===== -->
## Alternatives
- Managed Agents — rejected: needs hosted sandbox; target tests need the local machine
- Claude Code / Agent SDK subprocess — rejected: loads outside context; weaker tool control
