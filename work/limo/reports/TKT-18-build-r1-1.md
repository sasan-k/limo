---
ticket: TKT-18
plan_revision: 1
try: 1
result: done
last_passed: final check
---
# Build report TKT-18

## Steps
- STEP-4 ✅ verify passed (file already existed; verify run in this try)
- STEP-5 ✅ verify passed
- STEP-6 ✅ verify passed
- STEP-7 ✅ verify passed (27 FT-18 cases)
- STEP-8 ✅ verify passed (186 passed); `UnconfiguredHost` import removed from app.py (now unused)
- STEP-9 ✅ fmt, gates passed after 2 fix rounds: E501 in tests/contract/test_repo_hosts.py (line split); jscpd clones github.py/gitlab.py fixed by extracting limo/hosts/http.py (plan STEP-6 remedy); `mise run test` 186 passed
- final check: ✅ lint + FT-18 functional tests passed

## Files changed
- `engine/pyproject.toml` (edited)
- `engine/uv.lock` (edited)
- `engine/limo/config.py` (edited)
- `engine/limo/app.py` (edited)
- `engine/limo/hosts/repo_url.py` (created)
- `engine/limo/hosts/http.py` (created)
- `engine/limo/hosts/github.py` (created)
- `engine/limo/hosts/gitlab.py` (created)
- `engine/limo/hosts/router.py` (created)
- `engine/tests/contract/__init__.py` (created)
- `engine/tests/contract/test_repo_hosts.py` (created)
- `engine/tests/contract/fixtures/github/*.json` (created)
- `engine/tests/contract/fixtures/gitlab/*.json` (created)

## Stop reason
