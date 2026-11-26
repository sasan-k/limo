---
ticket: TKT-<n>
plan_revision: <n>
try: <n>
result: <done | stopped>
last_passed: <STEP-n | none>
---
# Build report TKT-<n>

## Steps
- STEP-1 ✅ verify passed
- STEP-2 ✅ verify passed (fixed once)
- STEP-3 ⛔ stopped
- final check: <✅ lint + functional tests passed | ⛔ | not reached>

## Files changed
<!-- Every file created/edited, repo-relative. Close uses this list as the diff scope. -->
- `<path>` (<created|edited>)

## Stop reason
<!-- only if stopped. Facts only, ≤ 10 lines. -->
- step: <STEP-n | final check>
- problem: <file not in context pack | instruction impossible/ambiguous | conflicts with code | verify fails after 1 fix>
- evidence: <error excerpt or file:line>
