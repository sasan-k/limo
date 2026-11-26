# Non-Functional Requirements — limo
<!-- Requirements that can't be a scenario. Architecture turns these into ADRs. -->

| ID | From | Category | Statement | Target | ADR |
|---|---|---|---|---|---|
| NFR-1 | REQ-1 | operability | Fresh clone runs with three mise commands; only mise installed globally | on a machine with only mise + git: UI reachable on 127.0.0.1 after the 3 commands, ≤ 10 min | pending |
| NFR-2 | REQ-2 | operability | Every task is discoverable | 100% of mise tasks listed by `mise run` with a description | pending |
| NFR-3 | REQ-3 | security | Secrets only from env/config, never persisted or sent to the model | a test key string appears 0 times in repo, db, logs, and recorded LLM requests | pending |
| NFR-4 | REQ-9 | architecture | Agent loop self-hosted on the Messages API | 100% of agent runs go through the engine's LLM port; no other LLM client | pending |
| NFR-5 | REQ-13 | portability | Commands run via the executor with `mise exec` in the workspace | 100% of agent commands go through the executor port (import-linter contract) | pending |
| NFR-6 | REQ-17 | architecture | Ticket state only via `fx` | 0 SQL statements on `tickets` outside `scripts/fx.py` | pending |
| NFR-7 | REQ-21 | maintainability | Scheduler replaceable | a second Scheduler implementation needs changes only in its own module + `app.py` | pending |
| NFR-8 | REQ-26 | portability | GitLab and GitHub supported | one RepoHost contract test suite passes for both adapters (recorded HTTP) | pending |
| NFR-9 | REQ-38 | performance | Live UI | state change visible in the UI ≤ 1 s, no reload | pending |
| NFR-10 | REQ-37 | usability | shadcn/ui components with one custom color theme, dark and light | every page renders with shadcn/ui components in both modes; mode toggle in the header; text contrast ≥ WCAG AA (4.5:1) | pending |
| NFR-11 | REQ-47 | scalability | Concurrency is a setting | `max_concurrent_tickets` = 1 by default; raising it needs no code change outside the runner's scheduling module | pending |
