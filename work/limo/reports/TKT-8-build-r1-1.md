---
ticket: TKT-8
plan_revision: 1
try: 1
result: stopped
last_passed: STEP-1
---
# Build report TKT-8

## Steps
- STEP-1 ✅ verify passed (earlier run, r0; not re-run)
- STEP-2 ⛔ stopped (before any edit)
- STEP-3..STEP-8 not reached
- final check: not reached

## Files changed
- `scripts/fx.py` (edited, from earlier try)

## Stop reason
- step: STEP-2
- problem: instruction conflicts with the plan's own later steps and verify
- evidence: STEP-2 `do` requires `FakeHost.create_issue` to return a ref with `.number`/`.url` (STEP-6 uses `ref.number`), which is the `IssueRef` type that only STEP-3 defines. `engine/limo/hosts/ports.py` has no `IssueRef` yet (grep: no match). Importing it in `engine/tests/fakes/host.py` would break all test imports, so the verify `mise run test:engine -- -k ft_8` could not FAIL for the stated reason ("no issues created"). No edits were made for STEP-2.
