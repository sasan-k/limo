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
