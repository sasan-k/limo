# Code Rules
<!-- Always read when writing or reviewing code. ≤ 60 lines. Each rule: one line, imperative, checkable. -->
<!-- Link the ADR that justifies a rule instead of explaining it: (ADR-n). Principles are expressed as concrete rules. -->

## Paradigm
- <e.g. OOP with constructor DI | functional core, imperative shell | …>
- <e.g. domain logic is pure; side effects only in adapters> (ADR-n)

## Structure (SOLID as project rules)
- SRP: <e.g. handlers only map transport ↔ domain; no business logic> — ref: `<file>`
- OCP: <e.g. new payment method = new strategy class, no switch on type> — ref: `<file>`
- DIP: <e.g. domain imports nothing from adapters/; deps injected via constructor>
- ISP: <e.g. ports are small, one per use case>
- LSP: <e.g. implementations honor the port's contract incl. errors>

## Reuse (DRY)
- shared helpers live in `<path>` — search there before writing new
- extract on the 3rd duplication, not the 2nd; no speculative abstractions
- one source of truth for constants, error codes, validation schemas: `<path>`

## Size & complexity
- function ≤ <40> lines · file ≤ <300> lines · cyclomatic complexity ≤ <10> · params ≤ <4>

## Patterns — use
- <pattern> — <where> — ref: `<file>`

## Patterns — avoid
- <anti-pattern> — <use instead>

## Naming
- files / types / functions / tests: <conventions>; domain names = glossary code names

## Errors · Validation · Logging
- errors: <raise/propagate/map> — ref: `<file>`
- validation: see security.md › Input
- logging: <logger, levels>; never PII or secrets

## Dependencies
- <e.g. no new libs without an ADR>

## Quality gates (Verify runs all; must pass)
- format/lint (incl. size & complexity rules): `<cmd>`
- duplication: `<cmd, e.g. jscpd --threshold 0 <changed files>>`
- architecture rules: `<cmd, e.g. dependency-cruiser / ArchUnit / import-linter>`
- types: `<cmd>`
