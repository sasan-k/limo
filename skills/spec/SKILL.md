---
name: factory-spec
description: Factory stage 1. Turn requirements into indexed REQs, BDD scenarios, glossary terms, NFRs, open questions and a ticket map (DAG). Re-run on requirement change.
argument-hint: <feature> [requirement files…]
---
# Spec (stage 1)

## Input
- requirement files (args) — copy into `work/<feature>/requirements/` if not there
- `context/INDEX.md`, `context/glossary.md` (always) · `context/adr/INDEX.md` (L1 only)
- re-run: existing `work/<feature>/` files — change only what the new requirements affect
- Tools: issue independent reads, lists and searches together in one turn; read line ranges when you
  know where to look. Every tool result stays in your context for every later turn.
- Read only these inputs; never search or read code (Plan does that).

## Output — `work/<feature>/` (templates in this skill dir: `templates/`)
`reqs.md` · `features/*.feature` · `nfr.md` · `questions.md` · `map.yaml` · updates to `context/glossary.md`

## Steps (in order; write each file before the next step)
1. **Index** → `reqs.md`. Split into atomic REQs. Kind F (behavior), N (non-functional), Q (unclear).
2. **Glossary** → add new domain terms to `context/glossary.md`. Use only glossary terms from here on.
3. **Questions** → every Q req and every ambiguity → `questions.md`. Never guess; mark what it blocks.
4. **NFRs** → every N req → `nfr.md` row, ADR column `pending`.
5. **Scenarios** → for each F req, scenarios in `features/<capability>.feature`.
6. **Tickets** → group scenarios into `map.yaml`.
7. **Check** → `fx map-check work/<feature>` and
   `fx trace-check work/<feature>`. Fix until OK.

## Scenario rules
- Tags: exactly one `@SC-n`, ≥ 1 `@REQ-n`. IDs permanent, never renumbered or reused.
- Concrete values (names, amounts, states). One behavior per scenario.
- Given: state reached through production actions — never "in the database".
- When: one user/system action. Then: externally observable (response, event, state read back).
- Cover the happy path and each business rule's positive AND negative outcome
  (e.g. insufficient balance → rejected). Technical negatives (auth, validation, not-found…)
  are NOT scenarios — Plan covers them in its operation matrix.
- Scenario blocked by an open question: still write it; after map-check, `fx set work/<feature> TKT-n status=blocked`.

## Ticket rules
- Ticket = smallest set of scenarios that delivers an observable outcome. ≤ 6 scenarios.
- Each scenario in exactly one ticket. `depends_on` only when a ticket truly needs another's behavior.
- `scope` from INDEX.md tags. New tickets start `todo` automatically. Re-run: never change done tickets (`fx status`) — add new ones.

## Done when
- [ ] map-check and trace-check print OK
- [ ] No scenario uses a term missing from glossary
- [ ] Every ambiguity is a question, not an assumption
