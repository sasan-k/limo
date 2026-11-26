# API & Contracts
<!-- Read when adding/changing endpoints, messages, or contracts. ≤ 60 lines. -->

## Style
- protocol: <REST+JSON | gRPC | GraphQL | …> (ADR-n)
- contract source of truth: `<openapi.yaml | *.proto | none>`
- versioning: <e.g. /v1 path prefix; breaking change = new version>

## Conventions
- naming: <e.g. plural nouns, kebab-case paths, camelCase fields>
- ids: <e.g. UUIDv7 strings>
- time: <e.g. ISO-8601 UTC>
- pagination: <scheme>
- idempotency: <e.g. Idempotency-Key header on POST>

## Errors
- shape: `<e.g. {"error":{"code":"...","message":"..."}}>`
- status mapping: <validation→400, not found→404, conflict→409, …>

## Auth
- <scheme, where enforced> — ref: `<file>`

## Events / messages
- broker: <name>; topic naming: <convention>
- envelope: `<shape>`; delivery: <at-least-once, consumers idempotent>

## Reference implementations
- endpoint: `<file>`
- consumer: `<file>`
