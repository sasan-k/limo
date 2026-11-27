---
ticket: TKT-15
feature: limo
scenarios: [SC-45]
scope: [ui, cost]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/ui.feature#SC-45, work/limo/reqs.md#REQ-44, context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, work/limo/plans/TKT-4.md#Design, engine/limo/api/cost_routes.py, engine/limo/cost/service.py:60-82, engine/limo/cost/repo.py:123-133, engine/tests/functional/test_cost.py, ui/src/**, ui/tests/harness.tsx]
---
# TKT-15: Cost view shows the four totals

## Design
- where: UI only — new `CostPage`, `CostTable`; shared `Select` (moved out of `PromptsPage`) and `useChosenProject` (moved out of `BoardPage`) so Board and Cost share project picking; nav gains `Cost`; SSE `cost.updated`/`run.finished` refetch `costs`. Engine unchanged (`GET /api/projects/{name}/costs`, TKT-4).
- responsibilities:
  - `ui/src/api/projects.ts` `useChosenProject()` — projects query + chosen project (first by default)
  - `ui/src/components/Select.tsx` — labelled native select (tokens only)
  - `ui/src/components/CostTable.tsx` — one total as label → `$x.xx` rows, or `No cost yet.`
  - `ui/src/pages/CostPage.tsx` — overall + per agent + per ticket + per agent on ticket
- reuse: `GET /api/projects/{name}/costs` → `CostTotals {per_agent, per_ticket, per_agent_ticket[{agent, ticket, cost}], overall}` (`engine/limo/api/cost_routes.py`); `formatUsd`; `getJson`; Vitest `serveApi`, `FakeEventSource`. Extraction of `Select`/`useChosenProject` is the 2nd use → avoids a jscpd clone.
- contracts: none new. UI query key `["costs", <project>]`; invalidated by `cost.updated` and `run.finished`.
- data: none
- decisions: follows ADR-2, ADR-13. No new ADR, no new dependency.

## Quality
### Security
- authn: n/a: ADR-7
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: n/a: no input besides choosing a listed project (name URL-encoded)
- injection: React escapes text; project name passed through `encodeURIComponent`
- data exposure / PII: dollar amounts, agent names, ticket ids only
- secrets: none
- rate limit / abuse: n/a: local single user
- audit: n/a: read only
### Performance
- queries (N+1, indexes): engine unchanged (one grouped query, TKT-4)
- pagination / limits: n/a: grouped totals, bounded by agents × tickets
- payload size: small (< 10 KB)
- caching: react-query, invalidated by SSE
- external calls (timeouts/retries): none
- sync vs async: n/a: UI only
- NFR targets: NFR-9 → FT-15.2 (cost.updated refetch); NFR-10 → FT-15.6 (axe both modes)

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 cost page `ui/src/pages/CostPage.tsx` | FT-15.1, FT-15.2, FT-15.3 | n/a: no input | FT-15.4 | n/a: read only | n/a: read only | n/a: read only | FT-15.6 | n/a: engine errors shown as in FT-15.4 |
| OP-2 cost totals `GET /api/projects/{name}/costs` (unchanged) | FT-15.5 | n/a: name only looked up (FT-4.9) | n/a: covered by FT-4.9 | n/a: read only | n/a: read only | n/a: read only | n/a: covered by FT-4.10 | n/a: no external call |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-15.1 | SC-45, OP-1:happy | `ui/tests/Cost.test.tsx` | `serveApi`: `/api/projects` → shop; costs → plan 1.000000, build 0.500000, TKT-1 1.500000, build on TKT-1 0.500000, overall 1.500000 | click nav `Cost` | rows: Per agent plan `$1.00`, build `$0.50`; Per ticket TKT-1 `$1.50`; Per agent on ticket `build on TKT-1` `$0.50`; `cost-overall` `$1.50` |
| FT-15.2 | OP-1:happy | same | costs empty | costs route now filled; `emit("cost.updated")` | `No cost yet.` first, then overall `$1.50` without reload |
| FT-15.3 | OP-1:happy | same | projects shop + blog (blog empty) | choose `blog` in `Project` | overall `$0.00` |
| FT-15.4 | OP-1:not-found | same | projects → `gone`, no costs route (404) | open Cost | text `GET /api/projects/gone/costs failed: 404` |
| FT-15.5 | SC-45, OP-2:happy | `engine/tests/functional/test_cost_view.py` | `add_cart_project`; `PUT /api/prices/claude-opus-5-5` `{"input": 4, "output": 20}`; `llm.script = [final_with(LlmUsage(250_000, 0))]`; `start_and_wait(client, "plan")`; `llm.script = [final_with(LlmUsage(125_000, 0))]`; `start_and_wait(client, "build")` | `GET /api/projects/shop/costs` | `per_agent == {"build": "0.500000", "plan": "1.000000"}`; `per_ticket == {"TKT-1": "1.500000"}`; `{"agent": "build", "ticket": "TKT-1", "cost": "0.500000"} in per_agent_ticket`; `overall == "1.500000"` |
| FT-15.6 | OP-1:boundary | `ui/e2e/cost.spec.ts` | e2e engine seeded with project `shop`, no runs | per mode: set `limo-theme`, reload, click `Cost` | `cost-overall` `$0.00`; region `Per agent` shows `No cost yet.`; axe `color-contrast` violations `[]` in both modes |

## Context pack
- `ui/src/pages/BoardPage.tsx` — use `useChosenProject` + `Select`
- `ui/src/pages/PromptsPage.tsx` — use shared `Select`
- `ui/src/api/types.ts`, `ui/src/api/events.ts`, `ui/src/App.tsx` — edit
- `ui/src/lib/format.ts` — `formatUsd` (read)
- `ui/tests/harness.tsx` — `serveApi`, `renderApp`, `FakeEventSource` (read)
- `ui/e2e/board.spec.ts` — e2e style to imitate
- `engine/tests/functional/test_cost.py:1-20` — imports and price constants to imitate
- `engine/tests/builders.py` — `add_cart_project`, `start_and_wait` (read)

## Steps
### STEP-1 Engine scenario test
- file: `engine/tests/functional/test_cost_view.py` (create)
- like: `engine/tests/functional/test_cost.py:1-20`
- do: `test_ft_15_5_cost_totals_match_the_scenario(client, llm, tmp_path)` with docstring `"""FT-15.5 …` exactly as in the table
- verify: `mise run test:engine -- -k ft_15` → 1 passed (engine already implements it)

### STEP-2 Cost component tests
- file: `ui/tests/Cost.test.tsx` (create)
- do: exact contents:
```tsx
import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { CostTotals } from "@/api/types";

import { FakeEventSource, renderApp, serveApi } from "./harness";

const SHOP: CostTotals = {
  per_agent: { build: "0.500000", plan: "1.000000" },
  per_ticket: { "TKT-1": "1.500000" },
  per_agent_ticket: [
    { agent: "build", ticket: "TKT-1", cost: "0.500000" },
    { agent: "plan", ticket: "TKT-1", cost: "1.000000" },
  ],
  overall: "1.500000",
};

const EMPTY: CostTotals = { per_agent: {}, per_ticket: {}, per_agent_ticket: [], overall: "0.000000" };

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

function row(table: string, label: string): string {
  const header = within(screen.getByRole("region", { name: table })).getByRole("rowheader", { name: label });
  return header.closest("tr")?.querySelector("td")?.textContent ?? "";
}

async function openCost(): Promise<void> {
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: "Cost" }));
  await screen.findByTestId("cost-overall");
}

test("FT-15.1 cost view shows the four totals of the project", async () => {
  serveApi({ current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/costs": SHOP } });
  await openCost();
  expect(row("Per agent", "plan")).toBe("$1.00");
  expect(row("Per agent", "build")).toBe("$0.50");
  expect(row("Per ticket", "TKT-1")).toBe("$1.50");
  expect(row("Per agent on ticket", "build on TKT-1")).toBe("$0.50");
  expect(screen.getByTestId("cost-overall")).toHaveTextContent("$1.50");
});

test("FT-15.2 cost.updated event refetches the totals without reload", async () => {
  const routes = {
    current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/costs": EMPTY } as Record<
      string,
      unknown
    >,
  };
  serveApi(routes);
  await openCost();
  expect(
    within(screen.getByRole("region", { name: "Per agent" })).getByText("No cost yet."),
  ).toBeInTheDocument();
  routes.current["/api/projects/shop/costs"] = SHOP;
  act(() => FakeEventSource.last?.emit("cost.updated"));
  await vi.waitFor(() => expect(screen.getByTestId("cost-overall")).toHaveTextContent("$1.50"));
});

test("FT-15.3 switching project loads that project's totals", async () => {
  serveApi({
    current: {
      "/api/projects": [{ name: "shop" }, { name: "blog" }],
      "/api/projects/shop/costs": SHOP,
      "/api/projects/blog/costs": EMPTY,
    },
  });
  await openCost();
  fireEvent.change(screen.getByLabelText("Project"), { target: { value: "blog" } });
  await vi.waitFor(() => expect(screen.getByTestId("cost-overall")).toHaveTextContent("$0.00"));
});

test("FT-15.4 unknown project shows the engine's message", async () => {
  serveApi({ current: { "/api/projects": [{ name: "gone" }] } });
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: "Cost" }));
  expect(await screen.findByText("GET /api/projects/gone/costs failed: 404")).toBeInTheDocument();
});
```
- verify: `mise run test:ui -- -t "FT-15"` → `FAIL: no button named "Cost"`

### STEP-3 Shared Select and project picker
- file: `ui/src/components/Select.tsx`, `ui/src/api/projects.ts` (create)
- do: `ui/src/components/Select.tsx`:
```tsx
/** Labelled native select styled with theme tokens. */
export function Select(props: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      {props.label}
      <select
        className="rounded-md border border-border bg-background px-2 py-1"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      >
        {props.options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}
```
  `ui/src/api/projects.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getJson } from "@/api/client";
import type { Project } from "@/api/types";

/** Project list plus the chosen project (the first one until the user picks another). */
export function useChosenProject() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => getJson<Project[]>("/api/projects") });
  const [chosen, setChosen] = useState<string | null>(null);
  const project = chosen ?? projects.data?.[0]?.name ?? null;
  const names = projects.data?.map((p) => p.name) ?? [];
  return { projects, names, project, setProject: setChosen };
}
```
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-4 Board and prompts use the shared pieces
- file: `ui/src/pages/BoardPage.tsx` (edit — replace whole file), `ui/src/pages/PromptsPage.tsx` (edit)
- do: `ui/src/pages/BoardPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import { useChosenProject } from "@/api/projects";
import type { Board } from "@/api/types";
import { Select } from "@/components/Select";
import { TicketCard } from "@/components/TicketCard";

function FeatureBoard({ board }: { board: Board }) {
  return (
    <>
      {board.features.map((feature) => (
        <section key={feature.name} aria-label={`feature ${feature.name}`} className="flex flex-col gap-3">
          <h2 className="font-semibold">{feature.name}</h2>
          <div className="grid auto-cols-[minmax(12rem,1fr)] grid-flow-col gap-3 overflow-x-auto">
            {board.statuses.map((status) => (
              <section
                key={status}
                aria-label={`${feature.name} ${status}`}
                className="flex flex-col gap-2 rounded-lg bg-muted p-2"
              >
                <h3 className="text-muted-foreground text-xs font-medium uppercase">{status}</h3>
                {feature.tickets
                  .filter((t) => t.status === status)
                  .map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} />
                  ))}
              </section>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

/** Tickets of every feature of one project, in one column per ticket status (REQ-40). */
export function BoardPage() {
  const { projects, names, project, setProject } = useChosenProject();
  const board = useQuery({
    queryKey: ["board", project],
    queryFn: () => getJson<Board>(`/api/projects/${encodeURIComponent(project ?? "")}/board`),
    enabled: project !== null,
  });
  if (projects.isPending) return <p className="text-muted-foreground">Loading projects…</p>;
  if (projects.isError) return <p className="text-destructive">Could not load projects.</p>;
  if (project === null) return <p className="text-muted-foreground">No projects yet.</p>;
  return (
    <div className="flex flex-col gap-4">
      <Select label="Project" value={project} options={names} onChange={setProject} />
      {board.isError && <p className="text-destructive">{board.error.message}</p>}
      {board.data && <FeatureBoard board={board.data} />}
    </div>
  );
}
```
  `ui/src/pages/PromptsPage.tsx`: delete the local `function Select(…) { … }` and add `import { Select } from "@/components/Select";` after the `PromptHistory` import (usage unchanged)
- verify: `mise run test:ui -- -t "FT-13|FT-14"` → all pass

### STEP-5 Cost page
- file: `ui/src/components/CostTable.tsx`, `ui/src/pages/CostPage.tsx` (create); `ui/src/api/types.ts`, `ui/src/api/events.ts`, `ui/src/App.tsx` (edit)
- do: `ui/src/components/CostTable.tsx`:
```tsx
import { formatUsd } from "@/lib/format";

/** One cost total as a two-column table: label → dollars. */
export function CostTable({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">No cost yet.</p>
      ) : (
        <table className="text-sm">
          <tbody>
            {rows.map(([label, amount]) => (
              <tr key={label} className="border-b border-border">
                <th scope="row" className="py-1 pr-4 text-left font-normal">
                  {label}
                </th>
                <td className="py-1 text-right font-mono">{formatUsd(amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```
  `ui/src/pages/CostPage.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";

import { getJson } from "@/api/client";
import { useChosenProject } from "@/api/projects";
import type { CostTotals } from "@/api/types";
import { CostTable } from "@/components/CostTable";
import { Select } from "@/components/Select";
import { formatUsd } from "@/lib/format";

function Totals({ costs }: { costs: CostTotals }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="text-lg">
        Overall <span data-testid="cost-overall">{formatUsd(costs.overall)}</span>
      </p>
      <div className="grid gap-6 md:grid-cols-3">
        <CostTable title="Per agent" rows={Object.entries(costs.per_agent)} />
        <CostTable title="Per ticket" rows={Object.entries(costs.per_ticket)} />
        <CostTable
          title="Per agent on ticket"
          rows={costs.per_agent_ticket.map((c) => [`${c.agent} on ${c.ticket}`, c.cost])}
        />
      </div>
    </div>
  );
}

/** The four cost totals of one project: per agent, per ticket, per agent on ticket, overall (REQ-44). */
export function CostPage() {
  const { projects, names, project, setProject } = useChosenProject();
  const costs = useQuery({
    queryKey: ["costs", project],
    queryFn: () => getJson<CostTotals>(`/api/projects/${encodeURIComponent(project ?? "")}/costs`),
    enabled: project !== null,
  });
  if (projects.isPending) return <p className="text-muted-foreground">Loading projects…</p>;
  if (projects.isError) return <p className="text-destructive">Could not load projects.</p>;
  if (project === null) return <p className="text-muted-foreground">No projects yet.</p>;
  return (
    <div className="flex flex-col gap-4">
      <Select label="Project" value={project} options={names} onChange={setProject} />
      {costs.isError && <p className="text-destructive">{costs.error.message}</p>}
      {costs.data && <Totals costs={costs.data} />}
    </div>
  );
}
```
  `types.ts`: add `export type CostTotals = components["schemas"]["CostTotals"];`. `events.ts`: `"run.finished"` list gains `["costs"]`; `"cost.updated"` becomes `[["agent-cards"], ["costs"]]`. `App.tsx`: import `CostPage` from `@/pages/CostPage`; `PAGES` gains `Cost: CostPage` as the last entry.
- verify: `mise run test:ui` → 18 passed

### STEP-6 E2E cost page
- file: `ui/e2e/cost.spec.ts` (create)
- like: `ui/e2e/board.spec.ts`
- do:
```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-15.6 cost page renders empty totals in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Cost" }).click();
    await expect(page.getByTestId("cost-overall")).toHaveText("$0.00");
    await expect(page.getByRole("region", { name: "Per agent" }).getByText("No cost yet.")).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
```
- verify: `mise run test:e2e` → all pass

### STEP-7 Format and full gates
- file: none (format only)
- do: `mise run fmt`
- verify: `mise run gates` → all pass; `mise run test` → all suites pass

## Do not
- change engine code; add packages; hard-code colors

## Doc updates
- context/layout.md: Wiring line — pages gain `Prompts`, `Cost`; shared UI pieces `ui/src/components/Select.tsx`, `ui/src/api/projects.ts` (`useChosenProject`)
- context/api.md: none
- context/glossary.md: none
- context/code-rules.md: none
- adr: none
- adr/INDEX.md: none
