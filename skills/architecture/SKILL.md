---
name: factory-architecture
description: Factory stage 0. Create or refresh the context/ snapshot and ADRs of a project. Modes - init-existing, init-new, refresh, nfr <feature>.
argument-hint: init-existing | init-new | refresh | nfr <feature>
---
# Architecture (stage 0)

Produce a small, accurate snapshot of the project in `context/` so planners start with the right map.

## Output (target project)
`context/INDEX.md stack.md layout.md api.md code-rules.md security.md performance.md data.md testing.md glossary.md adr/INDEX.md adr/ADR-n.md`
Templates: `templates/` in this skill dir. Read a template only when writing that file.

## Modes
**init-existing** — codebase → snapshot
1. Read manifests, build/CI config, top-level tree, entry points. Then 1–2 reference files per layer.
2. Fill each template from evidence only. Every rule/pattern cites a real file (`ref:`).
3. Existing conventions become `accepted` ADRs only if they are real decisions (protocol, persistence, messaging, auth, paradigm).
4. code-rules.md: SOLID/DRY only as concrete rules seen in 2+ places; Quality gates = tools already configured
   (missing tool → `<none>` + question proposing one).

**init-new** — inputs: requirements, NFRs, chosen stack (ask user if stack missing)
1. Write the snapshot as intended structure. Mark not-yet-existing paths `(planned)`.
2. Write ADRs for stack, protocol, persistence, paradigm, testing harness — status `accepted`.

**refresh** — fix drift
1. For each context file, check its claims against the code (paths exist, refs valid, versions match).
2. Fix wrong lines, add missing modules, delete stale lines. Edit as diffs, never rewrite whole files.
3. Report: `fixed: <file>: <change>` lines only.

**nfr <feature>** — `work/<feature>/nfr.md` rows with ADR `pending`
1. One ADR per decision needed (may cover several NFRs). Status `accepted` if forced by constraint, else `proposed` + question in `work/<feature>/questions.md`.
2. Set the ADR id in the nfr.md row. Add the L1 line to `adr/INDEX.md`.

## Rules
- Evidence only. Unknown → `<unknown>` + a question in `context/questions.md`, never invent.
- Each file ≤ 60 lines. Larger → split (e.g. `layout/<module>.md`) and link from INDEX.md routing table.
- One fact, one file. Others link to it. Snapshot states *what*; ADR states *why*.
- Point to code paths; never paste code except an ADR L3 pattern with no reference yet.
- Scope tags: only those in INDEX.md. Add a tag there first if truly needed.
- Read budget: grep/glob first; open files by line range; ≤ 30 files in init-existing.

## Done when
- [ ] Every template placeholder filled or marked `<unknown>`
- [ ] Every `ref:`/path exists (or marked `(planned)`)
- [ ] INDEX.md commands run (init-existing/refresh: run build + test once)
- [ ] Every ADR has an L1 line in adr/INDEX.md with matching status
