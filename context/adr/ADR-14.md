# ADR-14: Agents run as local `claude -p` sessions; tools come only from Limo's per-run MCP server
status: accepted
scope: agents, runner, cost
supersedes: none (extends ADR-6: the Messages API loop stays as backend `api`)
source: user decision 2026-11-27 (use the local Claude login instead of an API key)

<!-- ===== L2 ===== -->
## Decision
Setting `agent_backend` picks how a run executes: `claude-cli` (default) or `api` (ADR-6 loop).
`claude-cli` starts one `claude -p` process per run with the user's own Claude login and none of the
user's Claude setup, and gives it no built-in tools; its only tools are the agent's allowlisted Limo
tools, served for that run by the engine's MCP endpoint `POST /mcp/runs/{run_id}` behind a per-run token.

## Why
Use the developer's local Claude subscription (no API key) while keeping ADR-6's guarantees: isolated
context and tool limits enforced by the engine (Build reads only its context pack; resolver read-only).

## Rules
- MUST start `claude` with: `-p <task> --system-prompt-file skills/<agent>/SKILL.md --model <model>
  --tools "" --setting-sources "" --strict-mcp-config --mcp-config <per-run file>
  --allowedTools mcp__limo --permission-mode dontAsk --disable-slash-commands
  --no-session-persistence --output-format stream-json --verbose` (+ `--max-budget-usd` when a ticket budget applies)
- MUST NOT use `--safe-mode` (it also disables `--mcp-config` servers) nor `--bare` (it ignores the login)
- MUST run the process in an empty working directory outside any repo (`settings.agent_cwd`), stdin closed,
  env only `PATH` + `HOME` (no `ANTHROPIC_API_KEY`, no host tokens)
- MUST serve only the agent's allowlist on the MCP endpoint and run every call through `ToolBox.call`
  (same path limits, context pack, recording in `tool_calls` as ADR-6)
- MUST reject MCP calls whose token is wrong or whose run is no longer active (401)
- MUST record tokens and the CLI's `total_cost_usd` per run (billed cost, not the price table)
- MUST kill the process after `run_timeout_s`

<!-- ===== L3 ===== -->
## Consequences
- Claude Code still adds its own environment block (working dir, date, account email) and its built-in
  plugins; only `--bare` removes them and it needs an API key — accepted
- no `--max-turns` in the CLI: runs are capped by `run_timeout_s` and `--max-budget-usd`
- tests use a fake `AgentCli`; the adapter is covered by a contract test with a fake `claude` script
## Alternatives
- built-in Claude Code tools limited by flags — rejected: Build's context-pack limit becomes prompt-only
- `--bare` — rejected: requires `ANTHROPIC_API_KEY`
- replace the API backend — rejected: tests and API-key users keep `api`
