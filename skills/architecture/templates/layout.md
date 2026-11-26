# Layout
<!-- Read when locating code. ≤ 60 lines; split per module into layout/<module>.md if larger. -->
<!-- Paths are repo-relative. Point to real files; never paste code here. -->

## Tree
```
<top-level dirs only, 1 line comment each>
src/
  <module>/      # <owns what>
tests/
  functional/    # see testing.md
```

## Module anatomy
<the repeating structure inside a module — one line per layer>
- `<module>/<layer>/` — <what goes here, e.g. HTTP handlers / domain logic / repos>

## Where to put new things
| Adding a… | Goes in | Copy the pattern from |
|---|---|---|
| endpoint | `<path>` | `<reference file>` |
| domain logic | `<path>` | `<reference file>` |
| DB access | `<path>` | `<reference file>` |
| migration | `<path>` | `<reference file>` |
| event/message | `<path>` | `<reference file>` |
| functional test | `<path>` | `<reference file>` |

## Wiring
<where things get registered so they run: DI container, router, module index, config>
- `<file>` — <what is registered here>

## Do not touch
<generated code, vendored libs, legacy areas — with reason>
- `<path>` — <why>
