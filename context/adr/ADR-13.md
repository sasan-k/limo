# ADR-13: shadcn/ui theme via CSS variables, dark and light, AA contrast checked
status: accepted
scope: ui
supersedes: none
source: NFR-10

<!-- ===== L2 ===== -->
## Decision
One custom palette defined as shadcn/ui CSS variables for light and dark; a header toggle (system default) switches the `dark` class; contrast is checked in e2e.

## Why
NFR-10: consistent modern look in both modes with readable contrast.

## Rules
- MUST style only through theme tokens (CSS variables / Tailwind theme); no hard-coded colors in components
- MUST render every page in both modes in Playwright with an axe contrast check (WCAG AA)
- MUST persist the chosen mode in localStorage

<!-- ===== L3 ===== -->
## Consequences
- the palette itself is chosen in the first UI ticket and recorded in `ui/src/styles/theme.css`
