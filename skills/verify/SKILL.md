---
name: factory-verify
description: Factory stage 4. Run a ticket's functional tests, full suite, quality gates and trace check, review the diff against code rules, classify failures as build/plan/spec, and route the ticket within retry limits.
argument-hint: <feature> TKT-n
---
# Verify / Escalate (stage 4)

## Input
- `work/<feature>/map.yaml` (ticket) · `fx status work/<feature> TKT-n` (tries) · `context/INDEX.md` Commands
- `work/<feature>/plans/TKT-n.md` — Design, Quality, Functional tests, Steps
- Latest `work/<feature>/reports/TKT-n-build-*.md` (result, Files changed)
- Review only: `context/code-rules.md`, `context/security.md`; diff of Files changed (`git diff -- <files>` or read them)
- Tools: issue independent reads, lists and searches together in one turn; read line ranges when you
  know where to look. Every tool result stays in your context for every later turn.

## Steps
1. Build report `stopped` → skip to 6 with it as the failure.
2. **Tests:** ticket's functional tests (test-one per FT file), then full suite.
3. **Gates:** every command in code-rules.md › Quality gates, scoped to Files changed where supported.
4. **Trace:** `fx trace-check work/<feature> TKT-n --repo .`
5. **Review** (only if 2–4 pass) — the diff against this checklist, one finding per violation:
   - [ ] code-rules.md rules (structure, reuse, size, naming, errors, logging)
   - [ ] duplicates an existing helper instead of reusing it
   - [ ] plan's Quality answers actually implemented (authz, validation, limits, no PII in logs)
   - [ ] dead code, debug leftovers, TODOs, commented-out code
   - [ ] names match glossary code names
   Each finding cites the rule and `file:line`. No opinions without a rule.
6. **Classify** each failure/finding:
   - **build** — code doesn't do what the plan says (plan was right)
   - **plan** — following the plan can't pass, or the plan itself asked for the violation
   - **spec** — scenario contradictory, impossible, or conflicts with another
7. **Route** by worst class (spec > plan > build):
   | Class | Condition | Action |
   |---|---|---|
   | none | all pass, no findings | `set … status=verified` |
   | build | build_tries < 2 | `set … status=planned` (Build retries) |
   | build | build_tries ≥ 2 | treat as plan |
   | plan | plan_tries < 1 | `set … status=todo build_tries=0` (Plan revises) |
   | plan | plan_tries ≥ 1 | `set … status=blocked` → resolver (runner opens an incident), human only if it escalates |
   | spec | any | add question to `questions.md`, `set … status=blocked` |
8. Write `work/<feature>/reports/TKT-n-verify-r<rev>-<try>.md` (same `<rev>-<try>` as build report) from `templates/verify-report.md` (this skill dir).

`set …` = `fx set work/<feature> TKT-n …`

## Rules
- Do not fix code or tests. Diagnose only.
- Error excerpts ≤ 15 lines per failure; no full logs.
- Full-suite failures outside Files changed: class **plan** (regression the plan missed).
- Each failure/finding gets a one-line fix hint for the receiving stage.
