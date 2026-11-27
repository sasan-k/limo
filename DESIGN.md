# Software Factory — Design

Goal: deterministic, token-efficient pipeline from requirements to shipped code.
Diagrams: [ARCHITECTURE.md](ARCHITECTURE.md) — update it with any change here.

## Stages
0. Architecture — create/maintain the `context/` snapshot + ADRs
1. Spec — requirements → BDD + glossary + NFRs → ticket map
2. Plan — per ticket: design → functional tests → steps → context pack → doc updates
3. Build — light model follows the plan
4. Verify / Escalate — run tests, classify failures, route back
5. Close — apply doc updates, flip ADR status, mark ticket done

## Tasks per agent
**0. Architecture**
1. Turn an existing codebase into the snapshot (`context/` + initial ADRs)
2. Create snapshot for a new project from requirements/NFRs/chosen stack
3. Scan code and fix gaps/drift in the snapshot
4. Turn NFRs (from Spec) into ADRs

**1. Spec**
1. Requirements → BDD scenarios
2. Build/maintain glossary
3. Extract NFRs that can't be scenarios → `nfr.md`
4. Log ambiguities → `questions.md` (never guess)
5. Group scenarios into tickets → `map.yaml` (DAG)
6. On requirement change, update affected scenarios/tickets only

**2. Plan** (per ticket)
1. Read snapshot on demand, navigate code
2. Write design: where, contracts, data, decisions
3. Write proposed ADRs if a new decision is needed
4. Define functional tests (≥1 per scenario)
5. Write ordered steps, each with a verify command
6. Write context pack: exact files the builder may read
7. Write doc updates for snapshot + ADRs
8. On escalation, revise the plan from the failure report

**3. Build** (per ticket)
1. Follow steps in order, reading only the context pack
2. Run each step's verify command
3. Stop and report if a step can't be done as written — no improvising

**4. Verify / Escalate**
1. Run ticket's functional tests + existing suite
2. Check traceability: every scenario has a test, all pass
3. Classify failures: build / plan / spec
4. Route back with a short report, respecting retry limits

**5. Close**
1. Apply doc updates to snapshot
2. Check doc updates against actual code diff — code wins
3. Flip ADR status (proposed → accepted/rejected)
4. Mark ticket done in `map.yaml`

## Core rules
- **IDs + traceability:** `REQ-n → SC-n.m → TKT-n → FT/STEP`. Checked by script.
- **Never guess:** ambiguity → `questions.md`, skip or stop.
- **Single source of truth:** each fact lives in one file; others link.
- **Snapshot = now, ADR = why.** Snapshot links ADRs, never repeats reasoning.
- **Point, don't copy:** docs reference code paths instead of duplicating code.
- **Scripts over models** for anything mechanical (checks, status flips, ordering).
- **BDD scenarios:** concrete examples; `Given` reachable via production actions; `Then` observable externally; one behavior each; glossary terms only.
- **Functional tests:** exercise real production entry points; setup via production commands, never direct DB writes; fakes only at external boundaries.
- **Tickets:** smallest set of scenarios with observable value; each scenario in exactly one ticket; ≤6 scenarios; DAG via `depends_on`.

## Test coverage
- Spec: business positives + negatives as scenarios.
- Plan: operation matrix — every operation × fixed categories (context/testing.md `categories:`); each cell FT ids or `n/a: <reason>`.
- trace-check fails on any uncovered scenario, empty cell, or FT missing from code.

## Quality ownership
| Stage | Role |
|---|---|
| Architecture | defines: code-rules.md (SOLID/DRY as concrete rules, size limits, quality gate commands), security.md, performance.md |
| Plan | designs in: Reuse + Responsibilities in Design; Quality section (security + performance, every line answered) |
| Build | follows; cannot improve or deviate |
| Verify | enforces: quality gates (tools) + review of the diff against a fixed, rule-cited checklist |
| Close | learns: new conventions found via review → code-rules.md |

## ADR layering (on-demand reads)
- L1: `context/adr/INDEX.md` — one line per ADR + `scope:` tags (fixed vocabulary). Always read.
- L2: top of `ADR-n.md` — Decision, Why, Rules (must/must-not). Read when scope matches ticket.
- L3: bottom of `ADR-n.md` — context, alternatives, examples. Read only to apply a pattern or resolve a conflict.
- Plan records reads: `adr_read: [ADR-4:L2, ADR-7:L3]`.
- Status: proposed (Plan) → accepted/rejected (Close). Never edit accepted ADRs; supersede.

## Token budget rules
1. **Plan navigation:** follow `layout.md` paths; read budget (max files); grep + line ranges over whole files; log files read.
2. **Escalation limits:** 2 build tries → 1 re-plan → human. Failure reports carry only failing test + error.
3. **Spec scope:** one run per feature/epic; later runs read only `glossary.md` + `map.yaml`.
4. **Snapshot size:** ~60 lines per file, split beyond; Close edits as diffs; drift scan prunes.
5. **Plan terseness:** fixed sections, no prose; snippets only for non-obvious code.
6. **Caching:** `INDEX.md` + `code-rules.md` small and stable, placed first in prompts.
7. **Build isolation:** reads only the context pack; needing more = plan defect → stop.
8. **Skill size:** each `SKILL.md` < ~60 lines; templates loaded only when writing.
9. **Model tiering:** high model for Architecture/Spec/Plan/Verify (review); light model for Build and mechanical Close edits.
10. **Metrics:** log tokens per stage per ticket from day one.

## Runtime
- Claude Code skills: `/factory-architecture /factory-spec /factory-plan /factory-build /factory-verify /factory-close`.
- This repo = the factory. `./install.sh` links it to `~/.claude/factory` and skills to `~/.claude/skills/factory-*`.
- Target projects hold `context/` and `work/`.
- Model tiering is set by the caller (e.g. `claude -p --model …`), not by skills.

## Factory repo layout
```
skills/<stage>/SKILL.md + templates/
ARCHITECTURE.md    mermaid diagrams of this design
scripts/fx.py      map-check · trace-check · status · ready · set · adr (stdlib only; `scripts/fx` symlink; env FX_DB, FX_SCOPE)
install.sh
```

## Target project layout
```
context/
  INDEX.md  stack.md  layout.md  api.md  code-rules.md  security.md  performance.md  data.md  testing.md  glossary.md  questions.md
  adr/INDEX.md  adr/ADR-n.md
work/<feature>/
  requirements/  reqs.md  features/*.feature  nfr.md  questions.md  map.yaml
  plans/TKT-n.md
  incidents/TKT-n-<k>.md
  reports/TKT-n-build-r<rev>-<try>.md  TKT-n-verify-r<rev>-<try>.md  TKT-n-close.md  TKT-n-review-<k>.md  TKT-n-resolve-<k>.md
```

## IDs
`REQ-n` (reqs.md, kind F/N/Q) → `SC-n` (@tag) → `TKT-n` (map.yaml) → `OP-n` (plan operation) → `FT-<ticket>.<k>` (plan + test name) → `STEP-n` (plan).
An FT covers `SC-n` and/or `OP-n:<category>`.
`NFR-n` → `ADR-n`. `Q-n` in questions.md. IDs are never renumbered or reused.

## Ticket lifecycle
`todo → planned → built → verified → review → done` · side exits: `blocked` (human), `abandoned`.
| Stage | Sets |
|---|---|
| Plan | planned (revision: plan_tries +1) |
| Build | built + build_tries +1 (stopped: build_tries +1 only) |
| Verify | verified · planned (build retry, build_tries < 2) · todo + build_tries=0 (re-plan, plan_tries < 1) · blocked |
| Close | done · abandoned |

## Orchestration (in progress)
- **Limo = standalone app** (this repo). It hosts the agent prompts (today's skills) and builds each agent's whole context itself: its prompt + the task + its own tools. Nothing from `~/.claude`, CLAUDE.md, memory or other skills. Prompts link reference files (templates) by relative path.
- **Full solution, one repo:** anyone can clone it and run end to end (setup → add project → pipeline → MRs/PRs). Repo hosts via adapters (GitLab, GitHub).
- **Run locally, set up with mise:** `mise.toml` pins the app's tools (python, uv, node) and defines tasks (`mise run setup`, `mise run up`). Agents run commands on the host through an `Executor` interface (v1: local); in a target workspace they run via `mise exec`, so a project's own `mise.toml` installs its tools.
- **Agent loop = Messages API, self-hosted:** the Python engine runs each agent's loop with the Anthropic SDK and app-defined tools; per-agent tool allowlists enforce role limits (e.g. Build can read only its context pack).
- **Runner** (engine, no model): dispatches by ticket status (DB), one fresh agent run per stage, model per agent from config, logs token usage per run. Guard: status unchanged after a stage = stuck.
- **Ticket state in SQLite:** status + tries live in the engine DB, not `map.yaml` (which keeps definitions: id, title, scope, scenarios, deps). `fx` reads/writes the DB (stdlib `sqlite3`).
- **Scheduler: no Temporal in v1.** Durable state = SQLite (ticket state + runs table (id, ticket, agent, attempt, status, heartbeat)). On start: `running` → `interrupted`, reset workspace to the ticket branch's last commit, retry within limits. Waits (approval, CI, replies) = poll the host every few minutes (webhooks later). One ticket at a time. Behind a `Scheduler` interface so a durable engine can replace it.
- **Resolver agent** runs only when stuck (blocked, no status change, crash/timeout, limits hit, blocking question). Reads a script-built incident bundle; investigates read-only (repo + `host-query`), returns one allowlisted action as JSON, which the runner validates and applies: `retry <stage>` · `answer Q-n` · `edit-ticket` · `escalate`. Prompt: `skills/resolver/`. Incident bundle: `work/<feature>/incidents/TKT-n-<k>.md`.
- **Confidence:** act only with cited evidence + a known diagnosis category + `high`; else escalate. Never touches code, scenarios, accepted ADRs, retry history. Max 2 resolves per ticket. Report: `reports/TKT-n-resolve-<k>.md`.
- **Repo host (GitLab/GitHub):** each ticket mirrors to an issue (humans answer there; resolver reads replies) and gets its own MR/PR. The engine DB is the source of truth for status; the issue mirrors it.
- **Identity (Q-14):** Limo opens merge requests with its own token (bot account / app); a separate human approver approves. Adapter tests use recorded HTTP only (Q-13, ADR-12).
- **Merge = approval only:** the factory never merges on its own. Runner enables the host's "merge when approved + pipeline succeeds"; a ticket is `done` only once its MR is merged; dependents branch from the merged code.
- **Gates step:** Build may fix up to 3 gate-reported problems in the final gates step (lines the ticket changed only); other steps keep one fix attempt.
- **Partial reruns:** a revision whose earlier steps passed sets `run: from-STEP-n`; Build starts there.
- **Review status:** Close sets `review` (docs ship in the same MR/PR); runner sets `done` on merge. Changes requested → runner writes `reports/TKT-n-review-<k>.md`, ticket → `todo`; Plan decides: **fix pass** if every comment fits context-pack files with no contract/data/matrix change (appends `## Fix <k>`, `run: fix-<k>`, build_tries=0) else **re-plan** (plan_tries +1). Dependents wait; others continue.
- **Cost:** every agent run logs tokens (input, output, cache read/write) × a configurable price table → $. Totals per agent, per ticket, per agent×ticket, overall. Agent cards show the $ of the current ticket for that agent.
- **Runner switch:** UI button turns the runner on/off; starts off. Features start from a UI intake form. `work/<feature>/` (requirements, spec output, plans, reports) stays local in the workspace (`.git/info/exclude`), never committed; only code + `context/` ship in merge requests. Turning off lets the active run finish.
- **Budgets:** every ticket and every agent (per ticket) has a USD budget from configurable defaults. Reaching one stops work on the ticket and lists it in the inbox (no resolver); the user raises it and presses Continue.
- **Inbox Continue:** on an escalated ticket the user can type a response in Limo; it is posted on the issue and the resolver runs (not counted toward the limit). Issues carry status label `limo:<status>`.
- **Human only when really needed:** escalation = issue label `factory:needs-human` + diagnosis comment; runner continues other ready tickets.

## Build order
1. ✅ File formats (contracts between agents)
2. ✅ Skills, in pipeline order
3. ✅ Scripts
4. ✅ Orchestration design (above) + resolver prompt + fix pass
5. Limo app, built by the factory itself (`work/limo/`) — doubles as the dry run
