# Performance
<!-- Always read by Plan. ≤ 60 lines. Targets come from NFRs/ADRs; cite them. -->

## Budgets
| Path | Target | Source |
|---|---|---|
| REST reads (local) | p95 < 200 ms | stage-0 default; refine from NFRs |
| SSE event after state change | < 1 s | stage-0 default |
| UI first load (built) | < 2 s on localhost | stage-0 default |

## Data access
- no N+1: aggregate cost and run lists in one SQL query per view
- index every column used in WHERE/ORDER BY (runs by project+ticket+agent, usage by run)
- list endpoints paginated, default 50, max 200
- one SQLite connection per thread; WAL mode on

## Payloads
- run/tool logs returned truncated (≤ 20 KB per item) with a link to the full item

## Caching
- none server-side; UI caches via react-query, invalidated by SSE events

## External calls
- Claude API: streaming; SDK timeout + `max_retries` from config; no retry loops of our own on top
- repo hosts: timeout 10 s, 2 retries with backoff on 429/5xx for GET only
- polling repo hosts: every 3 min per waiting ticket, configurable
- no external calls while holding a db transaction

## Async
- agent runs execute in the runner's background worker, never inside an HTTP request
- one ticket at a time (DESIGN.md › Scheduler)

## How perf is verified
- functional: pagination caps and query counts where cheap
- load: none in v1
