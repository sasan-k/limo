# Incident TKT-7 #1
- trigger: limits (plan_tries 1, build stopped after revision 1)
- ticket: TKT-7 status planned, build_tries 1, plan_tries 1
- failure: FT-5.3 → 502 `git_failed` (test_runner.py:65 `assert 502 == 200`)
- reports: TKT-7-verify-r0-1.md, TKT-7-build-r1-1.md
