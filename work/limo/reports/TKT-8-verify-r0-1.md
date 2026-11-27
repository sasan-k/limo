---
ticket: TKT-8
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-8

## Results
- not run (build stopped at STEP-2)

## Failures & findings
### STEP-2 stop: intake endpoint not stated, not in the context pack
- class: plan
- rule: n/a (plan completeness)
- where: work/limo/plans/TKT-8.md FT-8.1
- why: "intake `posts`" names a production action without its route
- fix hint: state `POST /api/projects/shop/features {"name", "requirements"}`; add test_features.py as a `like:` file
