# Data
<!-- Read when adding/changing tables, fields, migrations. ≤ 60 lines. -->

## Stores
- <db name> — owns <what> — owned by module `<module>`

## Conventions
- table/collection naming: <convention>
- column naming: <convention>
- primary keys: <type>
- timestamps: <e.g. created_at/updated_at, UTC>
- soft delete: <yes/no, how>
- money/decimals: <representation>

## Migrations
- tool: <name>; location: `<path>`
- create: `<cmd>`; apply: `<cmd>`
- rules: <e.g. forward-only, no destructive change without ADR>

## Ownership
- a module only reads/writes its own tables; cross-module via <API/events> (ADR-n)

## Main entities
<!-- one line each; the schema files are the source of truth -->
- `<entity>` — <meaning> — `<schema/model file>`
