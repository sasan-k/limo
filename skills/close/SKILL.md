---
name: factory-close
description: Factory stage 5. After a ticket is verified (or abandoned), apply its doc updates to the context snapshot, reconcile them with the actual code, flip ADR statuses, and hand the ticket to review.
argument-hint: <feature> TKT-n [abandon]
---
# Close (stage 5)

## Input
- `work/<feature>/plans/TKT-n.md` — Design + Doc updates (+ `doc updates:` of any `## Fix <k>`; lines already applied are skipped)
- All `work/<feature>/reports/TKT-n-build-*.md` → union of **Files changed** (the diff scope; retries add files)
- Those files' changes: `git diff -- <files>` if the project uses git, else read the files
- Only the `context/` files named in section 6

## Steps — ship (ticket status `verified`)
1. For each doc-update line: compare with the actual code. Code wins; note differences as drift.
2. Apply each update to its `context/` file as a minimal edit. Keep files ≤ 60 lines (split if needed).
3. Proposed ADRs from this ticket: `fx adr context ADR-n accepted`
4. Superseded ADRs: `fx adr context ADR-m "superseded by ADR-n"`
5. Write `work/<feature>/reports/TKT-n-close.md` from [close-report](templates/close-report.md).
6. `fx set work/<feature> TKT-n status=review` — all of the above ships in the ticket's MR/PR; the runner sets `done` on merge.

## Steps — abandon
1. Proposed ADRs from this ticket → `fx adr context ADR-n rejected`
2. No snapshot changes. `fx set work/<feature> TKT-n status=abandoned`. Write close report.

## Rules
- Edit, never rewrite, context files. Touch only lines the update concerns.
- One fact, one file: if a fact already lives elsewhere, link instead of duplicating.
- Never edit an accepted ADR's content.
- Drift found beyond this ticket → list it in the report under Drift with `refresh needed`.
- Verify review findings fixed via a re-plan that reveal a missing convention → add one line to
  `context/code-rules.md` (cite the verify report).
