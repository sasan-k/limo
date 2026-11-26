# ADR-7: Local single-user app without authentication in v1
status: accepted
scope: auth, api
supersedes: none
source: stage-0

<!-- ===== L2 ===== -->
## Decision
No login in v1; the engine and dev UI bind to 127.0.0.1 only.

## Why
Clone-and-run local tool for one developer; humans act through the repo host (approvals, replies).

## Rules
- MUST bind servers to 127.0.0.1
- MUST NOT expose on another interface without a new ADR adding auth

<!-- ===== L3 ===== -->
## Consequences
- multi-user / hosted mode later needs auth + authz ADRs and matrix categories
