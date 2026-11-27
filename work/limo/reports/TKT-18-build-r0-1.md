---
ticket: TKT-18
plan_revision: 0
try: 1
result: stopped
last_passed: STEP-3
---
# Build report TKT-18

## Steps
- STEP-1 ✅ verify passed
- STEP-2 ✅ verify passed
- STEP-3 ✅ verify passed (expected FAIL: `ModuleNotFoundError`, test-first)
- STEP-4 ⛔ stopped (verify fails at collection; no fix attempted, see stop reason)
- final check: not reached

## Files changed
- `engine/pyproject.toml` (edited)
- `engine/limo/config.py` (edited)
- `engine/limo/hosts/repo_url.py` (created)
- `engine/tests/contract/__init__.py` (created)
- `engine/tests/contract/test_repo_hosts.py` (created)
- `engine/tests/contract/fixtures/github/*.json` (created, 11 files)
- `engine/tests/contract/fixtures/gitlab/*.json` (created, 10 files)

## Stop reason
- step: STEP-4
- problem: conflicts with code. The verify `mise run test:engine -- -k ft_18_9` cannot pass: `tests/contract/test_repo_hosts.py` imports `limo.hosts.github`, `limo.hosts.gitlab` and `limo.hosts.router` at module level (created in STEP-5..7), so collection fails before any FT-18.9 test runs. The only fix would be editing that test file's imports, which is outside this step's lines.
- evidence: `tests/contract/test_repo_hosts.py:9: from limo.hosts.github import GitHubHost` / `E   ModuleNotFoundError: No module named 'limo.hosts.github'` / `Interrupted: 1 error during collection` / `[test:engine] ERROR task failed` (exit 2)
