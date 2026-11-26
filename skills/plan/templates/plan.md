---
ticket: TKT-<n>
feature: <feature>
scenarios: [SC-<n>, …]
scope: [<tags>]
revision: <0 = first plan; n = after nth escalation>
run: <all | from-STEP-<n> | fix-<k>>  # which steps Build runs
read: [<every file read while planning, e.g. context/api.md, ADR-4:L2, src/orders/OrderService.ts:10-60>]
---
# TKT-<n>: <title>

## Design
- where: <modules/layers touched>
- responsibilities: <one line per new class/module: what it does, nothing else>
- reuse: <existing helpers/base classes/patterns used, with paths — or none found (searched <where>)>
- contracts: <new/changed endpoints, messages, schemas — exact shapes>
- data: <new/changed tables/fields/indexes, migration name>
- decisions: <follows ADR-n …> · <new: ADR-m proposed — one line>

## Quality
<!-- Every line answered: how it's handled, or `n/a: <reason>`. Rules: context/security.md, context/performance.md -->
### Security
- authn: …
- authz (permission/ownership): …
- input validation: …
- injection: …
- data exposure / PII: …
- secrets: …
- rate limit / abuse: …
- audit: …
### Performance
- queries (N+1, indexes): …
- pagination / limits: …
- payload size: …
- caching: …
- external calls (timeouts/retries): …
- sync vs async: …
- NFR targets: <NFR-n → how verified | none>

## Operation matrix
<!-- One row per operation added/changed. Columns = categories in context/testing.md, same order. -->
<!-- Each cell: FT ids (comma-separated) or `n/a: <reason>`. Never empty. -->
| Op | happy | validation | not-found | unauthenticated | forbidden | conflict | invalid-state | idempotency | boundary |
|---|---|---|---|---|---|---|---|---|---|
| OP-1 <name> `<entry point>` | FT-<t>.1 | FT-<t>.2, FT-<t>.3 | n/a: <reason> | FT-<t>.4 | FT-<t>.5 | n/a: <reason> | n/a: <reason> | FT-<t>.6 | FT-<t>.7 |

## Functional tests
<!-- Id: FT-<ticket number>.<k>. Covers: SC-n and/or OP-n:<category>, comma-separated. -->
<!-- Every scenario and every non-n/a matrix cell is covered. Rules: context/testing.md. Test name contains its id. -->
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-<t>.1 | SC-<n>, OP-1:happy | `<path>` | <setup calls> | <action> | <assertions> |

## Context pack
<!-- The ONLY files Build may read. Line ranges for files only imitated. -->
- `<path>`[:<from>-<to>] — <why>

## Steps
<!-- Ordered. One file or one concern per step. Tests first where practical. -->
### STEP-1 <title>
- file: `<path>` (<create|edit>)
- do: <exact instruction; signatures/names/types spelled out>
- like: `<reference file>` (optional)
```<lang>
<snippet only if non-obvious>
```
- verify: `<command>` → <expected result; test-first steps: `FAIL: <reason>`>

## Do not
- <things the builder must not change or add>

## Doc updates
<!-- Applied by Close before review. "none" is a valid value per line. -->
- context/<file>.md: <exact change>
- context/glossary.md: <terms or none>
- context/code-rules.md: <new convention or none>
- adr: <ADR-m proposed: title — or none>
- adr/INDEX.md: <line to add — or none>

## Fix <k>
<!-- Fix pass only: appended after review report TKT-n-review-<k>.md. Context-pack files only. -->
- comments: <review comment ids this fix answers>
### STEP-F<k>.1 <title>
- file: `<path from context pack>` (edit)
- do: <exact instruction>
- verify: `<command>` → <expected result>
- doc updates: <exact change or none>
