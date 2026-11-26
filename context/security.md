# Security
<!-- Always read by Plan. ≤ 60 lines. Each rule: one line, checkable, with ref or ADR. -->

## Identity
- authentication: none in v1; engine and dev UI bind to 127.0.0.1 only (ADR-7)
- authorization: n/a (single local user); any non-loopback bind requires a new ADR first
- CORS: allow only the UI origin; reject others

## Input
- validate at the boundary with pydantic models; reject unknown fields (`extra="forbid"`)
- queries: parameterized only; never build SQL, shell commands, or git refs from input strings
- commands: executor takes argv lists, never `shell=True`
- limits: request body ≤ 1 MB; prompt/ref file save ≤ 256 KB; list params max 200
- paths: every file path from input or from an agent tool is resolved and must stay inside its root
  (workspace, `skills/<agent>/`); reject symlinks escaping the root

## Agent tools (ADR-6)
- each agent gets only its allowlisted tools; the engine rejects any other tool name
- Build read tool: only files in the plan's Context pack; Resolver: read-only + host-query
- agents never receive API keys or host tokens; host access goes through engine tools
- write tools are confined to the project workspace; never the app's own repo except the prompt editor

## Data
- secrets: Anthropic key, GitLab/GitHub tokens from `.env` / environment only; never in code, db, logs, prompts, or fixtures
- PII: none stored beyond repo-host usernames in comments
- prompt bodies and diffs are not logged at INFO

## Abuse / runaway cost
- per-run caps: max agent turns and max tokens per run from config; exceeded → run fails, ticket stuck → resolver
- retry limits per DESIGN.md (2 build tries, 1 re-plan, 2 resolves)

## Audit
- every agent run, tool call (name + target path/command), resolver action, and prompt save is recorded in the db with time

## Error responses
- never return stack traces, SQL, or tokens; external errors map to 502 with a generic message + log id
