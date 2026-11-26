# ADR-9: Secrets only from the environment, never stored or sent to the model
status: accepted
scope: infra, agents, host
supersedes: none
source: NFR-3

<!-- ===== L2 ===== -->
## Decision
The Anthropic key and repo host tokens are read once from env (`.env` loaded by mise) into the settings object and passed only to the LLM and RepoHost adapters.

## Why
NFR-3: a canary key must appear 0 times in repo, db, logs, and LLM requests.

## Rules
- MUST hold secrets as `pydantic.SecretStr`; never `str`
- MUST NOT write secrets to the db, workspace, logs, SSE, API responses, or any Claude API request
- MUST redact secrets in subprocess env passed to the executor (agents' commands get none)
- MUST keep `.env` gitignored and ship `.env.example` without values

<!-- ===== L3 ===== -->
## Consequences
- functional test sets a canary key and greps db file, logs, workspace, and recorded fake-LLM requests
- git pushes use the token via a credential helper env var for that one subprocess only
