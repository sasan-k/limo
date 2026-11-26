# Security
<!-- Always read by Plan. ≤ 60 lines. Each rule: one line, checkable, with ref or ADR. -->

## Identity
- authentication: <scheme, e.g. OIDC JWT bearer> — enforced in `<file>`
- authorization: <model, e.g. RBAC roles + resource ownership> — enforced in `<file>`
- default: deny; every endpoint/consumer declares its required permission

## Input
- validate at the boundary with <lib/schema>; reject unknown fields: <yes/no> — ref: `<file>`
- queries: parameterized only; never build SQL/commands/templates from input
- limits: max body <size>, max string <len>, max list <n>

## Data
- PII fields: <list or pointer to data.md> — never logged, masked in responses unless owner
- secrets: from <vault/env>; never in code, logs, or test fixtures
- encryption: at rest <how>; in transit <TLS policy>

## Abuse
- rate limits: <scope + limit> — `<file>`
- idempotency for unsafe retries: <scheme> (see api.md)

## Audit
- audited actions: <which> — sink: <where> — fields: <who, what, when, target>

## Error responses
- never leak stack traces, SQL, internal ids; not-found vs forbidden: <policy, e.g. 404 for others' resources>
