import { act, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { card, FakeEventSource, renderApp, serveCards } from "./harness";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

function field(agent: string, name: string): string {
  const el = within(screen.getByTestId(`agent-card-${agent}`)).getByText(
    (_, node) => node?.getAttribute("data-field") === name,
  );
  return el.textContent ?? "";
}

test("FT-12.6 card shows model, state, ticket, cost and last run", async () => {
  serveCards({ current: [card()] });
  renderApp();
  await screen.findByTestId("agent-card-build");
  expect(screen.getByText("claude-haiku-5-5")).toBeInTheDocument();
  expect(field("build", "state")).toBe("idle");
  expect(field("build", "ticket")).toBe("TKT-1");
  expect(field("build", "cost")).toBe("$0.40");
  expect(field("build", "last run")).toBe("52,000 tokens");
  expect(field("build", "duration")).toBe("4 min");
  expect(field("build", "finished")).toBe("2026-11-26 14:05 UTC");
  expect(field("build", "tries")).toBe("1");
});

test("FT-12.7 run.started event turns the card active without reload", async () => {
  const cards = { current: [card()] };
  serveCards(cards);
  renderApp();
  await screen.findByTestId("agent-card-build");
  expect(FakeEventSource.last?.url).toBe("/api/events");
  cards.current = [card({ state: "active" })];
  act(() => FakeEventSource.last?.emit("run.started"));
  await vi.waitFor(() => expect(field("build", "state")).toBe("active"));
  expect(field("build", "ticket")).toBe("TKT-1");
});

test("FT-12.8 incident.opened event turns the card stuck without reload", async () => {
  const cards = { current: [card({ last_run: { ...card().last_run!, status: "failed" } })] };
  serveCards(cards);
  renderApp();
  await screen.findByTestId("agent-card-build");
  cards.current = [card({ state: "stuck" })];
  act(() => FakeEventSource.last?.emit("incident.opened"));
  await vi.waitFor(() => expect(field("build", "state")).toBe("stuck"));
});

test("FT-12.11 engine error shows a load error", async () => {
  serveCards({ current: [] }, 500);
  renderApp();
  expect(await screen.findByText("Could not load agents.")).toBeInTheDocument();
});
