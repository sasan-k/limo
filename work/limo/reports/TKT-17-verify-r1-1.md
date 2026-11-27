---
ticket: TKT-17
plan_revision: 1
build_try: 1
result: fail
route: build
---
# Verify report TKT-17

## Results
- not run (build stopped at STEP-1, nothing written)

## Failures & findings
### STEP-1 stop: did not read a `like:` file without a line range
- class: build
- rule: build SKILL.md › Input (now clarified: no range → whole file)
- where: engine/limo/api/cost_routes.py (in context pack)
- why: the price endpoint (`PUT /api/prices/{model}`) is in a pack file the builder skipped
- fix hint: read the whole `like:` file; retry the build (build_tries 1 < 2)
