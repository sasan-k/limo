# ADR-12: One RepoHost contract suite run against recorded HTTP for GitLab and GitHub
status: proposed
scope: host, testing
supersedes: none
source: NFR-8

<!-- ===== L2 ===== -->
## Decision
A single pytest contract suite exercises the RepoHost port; it runs against both adapters with recorded HTTP fixtures (respx), re-recordable against real sandbox repos.

## Why
NFR-8: both hosts must behave the same; recorded HTTP keeps tests free and offline.

## Rules
- MUST run every RepoHost contract test for both `gitlab` and `github`
- MUST store fixtures in `engine/tests/contract/fixtures/<host>/` with tokens scrubbed
- MUST NOT call real hosts in the default test run

<!-- ===== L3 ===== -->
## Alternatives
- Live sandbox repos in every run — rejected: needs tokens in CI, slow, flaky
## Open
- work/limo questions.md Q-13
