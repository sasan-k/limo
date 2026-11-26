---
ticket: TKT-1
plan_revision: 1
build_try: 1
result: fail
route: human
---
# Verify report TKT-1

## Results
- functional (ticket): 13/13
- full suite: 13/13 (`mise run test`)
- gates: lint ✅ · duplication ✅ · architecture ✅ · types ✅
- trace check: ok (`fx trace-check work/limo TKT-1 --repo .`)
- review: 2 findings

## Failures & findings
### R-1 engine venv runs Python 3.13, not the pinned 3.12
- class: plan
- rule: ADR-1 / stack.md › Runtime (Python 3.12, versions pinned in mise.toml)
- where: engine/pyproject.toml:4 (`requires-python = ">=3.12"`)
- why: `uv sync` picked Python 3.13.14; mise pins 3.12.16, so the app does not run on the pinned runtime
- error:
```
$ engine/.venv/bin/python --version
Python 3.13.14
```
- fix hint: set `requires-python = ">=3.12,<3.13"` (or `engine/.python-version` = `3.12`), rerun `mise run setup`

### R-2 `git rev-parse` result not checked
- class: plan
- rule: code-rules.md › Errors (services raise typed errors)
- where: engine/limo/projects/service.py:37
- why: a failing rev-parse would save the project with `default_branch` "" and no error
- error:
```
branch = self._executor.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path, self._timeout_s)
```
- fix hint: code ≠ 0 or empty output → rmtree workspace, raise `ExternalError("clone_failed", …)`

Route: plan class with plan_tries 1 ≥ 1 → blocked → human.
