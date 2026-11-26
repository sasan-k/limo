# Limo — requirements (input to /factory-spec limo)

Source of decisions: DESIGN.md "Orchestration (in progress)". This file states what the app must do.

## Product
Limo: a standalone app in this repo that runs the factory agents end to end on a target project. Anyone can clone it and run it.

## Setup and run
- `mise install && mise run setup && mise run up` installs pinned tools (python, uv, node) and starts engine + UI on localhost.
- `mise run` lists all tasks.
- Config: Anthropic API key, repo host token (GitLab or GitHub), price table, model per agent. Secrets are never committed.
- Add a target project by git URL; the app clones it into a workspace.

## Agents
- Agents: architecture, spec, plan, build, verify, close, resolver. Each = prompt file + reference files (templates) linked by relative path.
- Each run's context is built only from: the agent's prompt, the task (feature, ticket), and the agent's tools. Nothing from `~/.claude`, CLAUDE.md, memory or other skills.
- Agent loop runs in the engine on the Claude Messages API (self-hosted).
- Each agent has a tool allowlist enforced by the engine. Build can read only the files in its plan's context pack. Resolver is read-only plus host-query.
- Model per agent is configurable.
- Commands run on the host through an Executor interface (v1 local); in a workspace via `mise exec`.

## Runner and scheduler
- Dispatches by ticket status: todo (deps done) → plan; planned → build; built → verify; verified → close; review → wait for merge.
- Before tickets: architecture init if `context/` is missing; spec; map-check; architecture nfr if NFRs exist.
- One ticket at a time. Fresh agent run per stage.
- Ticket status and tries live in SQLite (via `fx`); map.yaml holds definitions only.
- Runs table: id, ticket, agent, attempt, status, heartbeat. On start, `running` runs become `interrupted`, the workspace is reset to the ticket branch's last commit, and the stage is retried within limits.
- Stuck = blocked, stage ended with no status change, crash, timeout, retry limits hit, or a blocking question.
- Waits (approval, CI, human replies) are polled on the repo host every few minutes.
- Scheduler sits behind an interface so a durable engine can replace it.

## Resolver
- Runs only when a ticket is stuck. The runner writes an incident bundle; the resolver returns one JSON action.
- Runner validates the action against the allowlist (retry, answer, edit-ticket, escalate) and applies it.
- Max 2 resolves per ticket; then escalate.
- Escalation: issue label `factory:needs-human` + diagnosis comment; runner continues other ready tickets.

## Repo host
- Adapter interface with GitLab and GitHub implementations: issues, MR/PR, labels, comments, approvals, CI status.
- Each ticket mirrors to an issue (status in sync); humans answer on the issue; their replies reach the resolver.
- Each ticket gets its own branch and MR/PR. Close output ships in the same MR/PR.
- The factory never merges: it enables the host's merge-when-approved-and-pipeline-succeeds. Ticket becomes `done` when merged. Dependents branch from the merged code.
- Changes requested → review comments saved to a review report → ticket back to plan (fix pass or re-plan, decided by Plan).

## Cost
- Every agent run logs input, output, cache read and cache write tokens and the model.
- $ = tokens × configurable price table.
- Totals: per agent, per ticket, per agent×ticket, overall.

## UI
- Simple, modern, live (updates without reload).
- One card per agent: name, model, state (idle / active / stuck), current ticket, $ spent by this agent on the current ticket, last run (tokens, time, tries).
- Ticket board by status with dependencies; needs-human inbox.
- Prompt editor: view and edit each agent's prompt and reference files; every save is versioned in git and can be rolled back.
- Cost view with the four totals.
