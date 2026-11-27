---
ticket: TKT-7
plan_revision: 2
build_try: 1
result: fail
route: build
---
# Verify report TKT-7

## Results
- full suite: 87/87 · gates: lint ❌ (S608) · types/arch/dup not reached

## Failures & findings
### gate: lint S608
- class: build
- rule: code-rules.md › Patterns — use (SQL parameterized, literal)
- where: engine/limo/hosts/repo.py:71
- why: SQL built with an f-string (`f"SELECT {_COLUMNS} …"`); the plan asked for plain parameterized SQL
- fix hint: write the column list literally inside the SQL string; no f-string in SQL
