# ADR Index
<!-- L1. Always read by Plan. One line per ADR. Status: proposed | accepted | rejected | superseded. -->
<!-- Format: - ADR-<n> [<status>] <decision in ≤ 10 words> — scope: <tags from INDEX.md> -->

- ADR-1 [accepted] Python FastAPI engine, React TS UI, mise tooling — scope: infra, ui
- ADR-2 [accepted] REST + JSON, SSE for live updates — scope: api, ui
- ADR-3 [accepted] Single SQLite file, plain SQL, forward-only migrations — scope: persistence
- ADR-4 [accepted] Ports and adapters, constructor injection — scope: runner, agents, host, infra
- ADR-5 [accepted] Functional tests via HTTP, fakes only external — scope: testing
- ADR-6 [accepted] Self-hosted Messages API loop, isolated context, enforced tools — scope: agents
- ADR-7 [accepted] Local single-user, no auth in v1 — scope: auth, api
- ADR-8 [accepted] mise tasks are the only developer interface — scope: infra
- ADR-9 [accepted] Secrets from env only, never stored or sent — scope: infra, agents, host
- ADR-10 [accepted] Executor runs argv via mise exec in workspace — scope: agents, infra
- ADR-11 [accepted] Scheduler port, concurrency setting, v1 in-process — scope: runner
- ADR-12 [accepted] One RepoHost contract suite on recorded HTTP — scope: host, testing
- ADR-13 [accepted] shadcn/ui theme tokens, dark/light, AA checked — scope: ui
- ADR-14 [accepted] Agents run via local claude -p; tools only via Limo MCP — scope: agents, runner, cost
