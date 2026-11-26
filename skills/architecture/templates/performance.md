# Performance
<!-- Always read by Plan. ≤ 60 lines. Targets come from NFRs/ADRs; cite them. -->

## Budgets
| Path | Target | Source |
|---|---|---|
| <e.g. API reads> | <p95 < 200 ms> | NFR-n / ADR-n |
| <e.g. API writes> | <p95 < 400 ms> | |

## Data access
- no N+1: load related data in one query/batch — ref: `<file>`
- every lookup/filter column is indexed; new query on unindexed column → migration adds index
- list endpoints: paginated, default <n>, max <n>
- select only needed columns for lists

## Payloads
- max response size: <n>; large exports are async

## Caching
- <what is cached, where, TTL, invalidation> — or: none (ADR-n)

## External calls
- timeout: <ms>; retries: <n with backoff>, only for idempotent calls
- no external calls inside DB transactions

## Async
- work > <n ms> or not needed for the response → <queue/job> — ref: `<file>`

## How perf is verified
- functional: query-count / pagination-cap assertions where cheap
- load: `<cmd/tool>` for budget checks (not part of the functional suite)
