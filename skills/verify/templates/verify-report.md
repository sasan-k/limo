---
ticket: TKT-<n>
plan_revision: <n>
build_try: <n>
result: <pass | fail>
route: <none | build | plan | spec | human>
---
# Verify report TKT-<n>

## Results
- functional (ticket): <passed>/<total>
- full suite: <passed>/<total>
- gates: <lint ✅ · duplication ✅ · architecture ✅ · types ✅>
- trace check: <ok | errors>
- review: <n findings | skipped (earlier failure)>

## Failures & findings
<!-- One block each. Error excerpt ≤ 15 lines. No full logs. -->
### <FT-id | gate name | R-n review finding>
- class: <build | plan | spec>
- rule: <code-rules.md › section | security.md › section | n/a for test failures>
- where: <file:line>
- why: <one line>
- error:
```
<excerpt>
```
- fix hint: <one line for the receiving stage>
