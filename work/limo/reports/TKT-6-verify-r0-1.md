---
ticket: TKT-6
plan_revision: 0
build_try: 1
result: fail
route: plan
---
# Verify report TKT-6

## Results
- full suite: 86/100 (build report STEP-9) · gates not reached

## Failures & findings
### 14 failures: ship → 502 git_failed once `work/` is in `.git/info/exclude`
- class: plan
- rule: n/a (full suite green)
- where: engine/limo/vcs/git.py (`git add -A -- . ':(exclude)work'`)
- why: git exits 1 when a pathspec names an ignored path ("paths are ignored by one of your .gitignore files: work"); reproduced in a scratch repo. TKT-7's add command and TKT-6's exclude cannot coexist; the plan forbade touching shipping
- error:
```
The following paths are ignored by one of your .gitignore files:
work
exit 1
```
- fix hint: `git add -A` then `git reset -q -- work` (unstages tracked `work/` changes; untracked ones are already ignored)
