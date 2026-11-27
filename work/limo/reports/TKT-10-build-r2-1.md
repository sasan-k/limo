---
ticket: TKT-10
plan_revision: 2
try: 1
result: stopped
last_passed: STEP-7
---
# Build report TKT-10

## Steps
- STEP-1..STEP-7 ✅ passed in earlier runs (not re-run; trusted per `run: from-STEP-8`)
- STEP-8 ⛔ stopped before any edit (conflicts with code)
- STEP-9 not reached
- STEP-10 not reached
- final check: not reached

## Files changed
<!-- Cumulative for TKT-10 (from git status at run start); this run changed no files. -->
- `engine/limo/hosts/ports.py` (edited)
- `engine/limo/hosts/unconfigured.py` (edited)
- `engine/tests/fakes/host.py` (edited)
- `engine/limo/incidents/apply.py` (edited)
- `engine/limo/incidents/models.py` (edited)
- `engine/limo/incidents/repo.py` (edited)
- `engine/limo/incidents/service.py` (edited)
- `engine/tests/functional/test_escalations.py` (created)
- `engine/limo/store/migrations/012_escalations.sql` (created)

## Stop reason
- step: STEP-8
- problem: conflicts with code
- evidence:
  - STEP-8 changes `IncidentRepo.escalations()` to return a 4-tuple with `created_at`, but `engine/limo/incidents/service.py:157` unpacks `row, name, feature = match` (3 names). `service.py` is not in STEP-8's `file:` list, so the step cannot be applied without changing a file it does not name.
  - `engine/limo/incidents/repo.py:85-94`: the current `escalations()` SELECT returns `project` and `feature` columns, and `_row()` (`repo.py:214-222`) passes all keys to `IncidentRow(**...)`, which has no such fields, so `escalations()` raises `TypeError` today.
  - STEP-8 `do:` also edits `engine/limo/common/errors.py`, which is not in its `file:` list (context pack lists it as read only).
  - Needs a plan revision (name `service.py` and `errors.py` in STEP-8, and fix the `_row` keys).
