---
ticket: TKT-19
plan_revision: 1
build_try: 1
result: fail
route: build
---
# Verify report TKT-19

## Results
- full suite: 138/138 · gates: lint ❌ (13 × E501 in test_resolver_actions.py)

## Failures & findings
### gate: lint E501
- class: build
- rule: code-rules.md › Quality gates; build SKILL.md gates exception (clarified: 3 fix *rounds*, each fixing everything one gate run reports)
- where: engine/tests/functional/test_resolver_actions.py (13 lines)
- why: the builder read "3 problems" as 3 lines
- fix hint: move long JSON action strings into module-level constants built with `json.dumps(...)`; wrap the rest
