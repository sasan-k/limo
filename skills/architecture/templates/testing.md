# Testing
<!-- Read when defining functional tests. ≤ 60 lines. -->

## Functional tests mimic production
- enter only through real production entry points: <HTTP API | queue | CLI>
- set up state only through production actions (API calls/commands), never direct DB writes
- assert only externally observable results: responses, emitted events, state read back via the API
- fake only external boundaries listed below; everything inside the system is real

## Operation matrix categories
<!-- Plan fills one cell per category for every operation. Parsed by fx.py — keep on one line. -->
categories: happy, validation, not-found, unauthenticated, forbidden, conflict, invalid-state, idempotency, boundary
- happy: valid request succeeds, effects observable
- validation: one test per validation rule
- not-found: target missing (or other tenant's → per security.md policy)
- unauthenticated: no/invalid credentials
- forbidden: authenticated but lacks permission/ownership
- conflict: duplicate/unique violation/version mismatch
- invalid-state: action not allowed in current state
- idempotency: same request retried → single effect
- boundary: min/max/empty values, pagination caps

## Harness
- location: `<path>`; runner: <name>; run one: `<cmd>`
- app under test starts via: <in-process | docker compose | testcontainers>
- isolation: <e.g. fresh DB schema per test file / unique tenant per test>
- reference test: `<file>`

## Fakes (external boundaries only)
| External system | Fake | Location |
|---|---|---|
| <payment provider> | <stub server / in-memory> | `<path>` |

## Test data
- builders/helpers: `<path>` — reuse before adding new
- no shared mutable fixtures between tests

## Naming
- file: `<convention>`; test name contains its FT id, e.g. `FT-12.1 <behavior>`

## Other suites
- unit: `<path>`, run `<cmd>` — optional, plan decides
- full suite: `<cmd>` — must stay green
