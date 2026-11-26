---
name: factory-plan
description: Factory stage 2. For one ticket, write a complete implementation plan (design, quality, operation matrix, functional tests, context pack, steps, doc updates) that a light model can follow without exploring. Also revises a plan after escalation.
argument-hint: <feature> TKT-n
---
# Plan (stage 2)

You are the only stage that designs. Build follows your plan literally and reads nothing else.

## Input (in this order, stop when you have enough)
1. `work/<feature>/map.yaml` (this ticket) + its scenarios in `work/<feature>/features/`
2. Always: `context/INDEX.md`, `code-rules.md`, `security.md`, `performance.md`, `testing.md`, `adr/INDEX.md`
3. Context files the INDEX routing table names for this ticket's scope
4. ADR L2 for every ADR whose scope matches; L3 only to apply its pattern or resolve a conflict
5. Plans of `depends_on` tickets — Design section only
6. Code: reference files from layout.md first; grep + line ranges; ≤ 15 code files
Revision (plan exists): read latest `work/<feature>/reports/TKT-n-verify-*.md`; change only what it requires; `revision` +1.
  Steps before the first changed step passed and are untouched → set `run: from-STEP-n` (n = first changed step); else `run: all`.
Review (`work/<feature>/reports/TKT-n-review-<k>.md` newer than the plan):
- **Fix pass** if every comment can be met by editing files already in the Context pack, with no change to
  Design contracts/data or the operation matrix → append `## Fix <k>` (template), set `run: fix-<k>`.
- Otherwise → full revision as above, `run: all`. Unclear comment → question on the MR/PR, set `blocked`, stop.

## Output
`work/<feature>/plans/TKT-n.md` from `templates/plan.md` (this skill dir). Proposed ADRs → `context/adr/ADR-n.md` + L1 line.

## Rules — design
- Follow code-rules.md and accepted ADRs. Conflict → write a question, set ticket `blocked`, stop.
- Reuse first: grep shared paths for existing helpers before designing new code; record what you searched.
- One responsibility per new class/module. No speculative abstractions or interfaces.
- New decision (pattern, lib, protocol, data ownership) → ADR `proposed`. Otherwise no ADR.
- Quality: answer every Security and Performance line; `n/a: <reason>` only if truly not applicable.

## Rules — tests
- Operation matrix: one row per operation the ticket adds or changes; every category cell filled.
- Every applicable Quality item that is testable (authz, validation, limits) has a matrix cell test.
- Functional tests: follow testing.md; each scenario and non-n/a cell covered; name contains FT id.
- Test steps spell out how to read each result (exact JSON paths, e.g. the error envelope).

## Rules — steps
- Context pack: every file a step edits or imitates (line ranges for imitated). Nothing else.
- Ordered, one file/concern each; exact names, signatures, types; snippet only when non-obvious.
- Every step has `verify` with expected result. Tests before the code they test (`FAIL: <reason>`).
- Wiring (routes, DI, registration, migrations) as explicit steps.
- Doc updates: every snapshot change, as exact lines; `none` where nothing changes.
- No prose beyond the template.

## Finish
1. `fx trace-check work/<feature> TKT-n` → OK
2. `fx set work/<feature> TKT-n status=planned` (revision: also `plan_tries=+1`; fix pass: `build_tries=0` instead)

## Done when
- [ ] trace-check OK; every step uses only context-pack files
- [ ] A reader with only this plan + context pack could implement it without guessing
