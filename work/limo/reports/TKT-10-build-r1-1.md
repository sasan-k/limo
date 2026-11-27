---
ticket: TKT-10
plan_revision: 1
try: 1
result: stopped
last_passed: STEP-7
---
# Build report TKT-10

## Steps
- STEP-6 ✅ verify passed (revision 1: run_failed parameter, escalate(summary, ask))
- STEP-7 ✅ verify passed (IncidentDeps gained host, issues, projects; see Notes)
- STEP-8 ⛔ stopped
- STEP-9 not reached
- STEP-10 not reached
- final check: not reached

## Files changed
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/tests/functional/test_escalations.py` (created)
- `engine/limo/store/migrations/012_escalations.sql` (created)
- `engine/limo/incidents/models.py` (edited)
- `engine/limo/incidents/repo.py` (edited)
- `engine/limo/incidents/apply.py` (edited)
- `engine/limo/incidents/service.py` (edited)

## Stop reason
- step: STEP-8
- problem: instruction conflicts with code. STEP-8 says `RunnerService.inbox()` orders escalations by `created_at`, but the STEP-5 contract `IncidentRepo.escalations()` returns `(IncidentRow, project name, feature)` with no timestamp, and `IncidentRow` has no `created_at` field.
- evidence: `engine/limo/incidents/repo.py:82-94` (escalations SELECT has no created_at); `engine/limo/incidents/models.py:20-34` (IncidentRow fields); `engine/limo/incidents/repo.py:19-34` (`incidents.created_at` is written on add)

## Notes
- STEP-7 added `host: RepoHost`, `issues: IssueRepo`, `projects: ProjectRepo` to `IncidentDeps` (the plan allowed host/issues there; projects is needed by `answer()` to resolve the project id). STEP-9 must pass them in `engine/limo/app.py`.
- STEP-7 wraps `HostError` from `escalate` (limit path) and `issue_comments`/`comment_issue` in `ExternalError("host_error")`.
