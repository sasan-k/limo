---
name: factory-build
description: Factory stage 3. Implement one ticket by following its plan step by step, reading only the plan's context pack. Stops and reports instead of improvising.
argument-hint: <feature> TKT-n
---
# Build (stage 3)

Follow the plan exactly. You do not design, explore, or improve.

## Input
- `work/<feature>/plans/TKT-n.md`
- Only the files listed in its **Context pack**:
  - file a step edits → read the whole file
  - file only imitated (`like:`) → read only its line range; no range given → read the whole file
  - file marked `read` → read it whole; it may show routes, helpers and signatures your steps need
  - files any step of this plan creates or edits (`file:` lines) are always yours to read and fix
- `context/INDEX.md` → **Commands** section only
- Tools: issue independent reads, lists and searches together in one turn; read line ranges when you
  know where to look. Every tool result stays in your context for every later turn.

## Output
- Code and tests changed as the steps say. No commit.
- `work/<feature>/reports/TKT-n-build-r<rev>-<try>.md` from `templates/build-report.md` (this skill dir)
  `<rev>` = plan `revision`; `<try>` = `build_tries` from `fx status work/<feature> TKT-n` + 1

## Steps
Run the steps the plan's `run:` names — `all`: every STEP under Steps; `from-STEP-<n>`: STEP-n and the ones after it
(earlier steps already passed; trust their files); `fix-<k>`: only the steps under `## Fix <k>`.
For each of those steps in order:
1. Do exactly what `do:` says in `file:`. Use names, types and snippets as written;
   change a snippet only where the step says to.
2. Run its `verify` command and compare with the expected result.
   - Expected `FAIL` (test-first step) and it fails for the stated reason → pass.
3. Pass → next step. Otherwise one fix attempt, then re-verify. Still failing → stop.
   Exception: a step whose verify runs the quality gates gets up to 3 fix rounds; in each round fix everything
   one gate run reports (only on lines this ticket created or changed), then rerun the gates.

A fix attempt may change only lines this step created or changed.
It never changes a test's assertions or expected values.

After the last step:
1. Run lint/format.
2. Run the ticket's functional tests (test-one command per FT file).
3. A failure here → stop with the last step = `final check`.

## Stop (write report with result `stopped`) when
- A step needs a file not in the context pack
- An instruction is impossible, ambiguous, or conflicts with the code
- A verify still fails after one fix attempt

On stop, leave the code as it is (no rollback). The report names the last step that passed.

## Rules
- Never read files outside the context pack. Never search the codebase.
- Never change files not named in a step. Never add steps, refactors, comments or extras.
- Respect the plan's **Do not** list.
- Report facts only; error excerpts ≤ 10 lines.

## Finish
- Done: `fx set work/<feature> TKT-n status=built build_tries=+1`
- Stopped: `fx set work/<feature> TKT-n build_tries=+1`
