import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { Board, InboxItem } from "@/api/types";

import { FakeEventSource, renderApp, serveApi } from "./harness";

const STATUSES = ["todo", "planned", "built", "verified", "review", "done", "blocked", "abandoned"];

function board(tkt1Status: string): Board {
  return {
    project: "shop",
    statuses: STATUSES,
    features: [
      {
        name: "cart",
        tickets: [
          {
            id: "TKT-1",
            title: "Cart shows a total",
            status: tkt1Status,
            depends_on: [],
            build_tries: 0,
            plan_tries: 0,
          },
          {
            id: "TKT-2",
            title: "Cart total includes tax",
            status: "todo",
            depends_on: ["TKT-1"],
            build_tries: 0,
            plan_tries: 0,
          },
        ],
      },
    ],
  };
}

const ESCALATION: InboxItem = {
  id: "inc-1",
  project: "shop",
  feature: "cart",
  ticket: "TKT-1",
  kind: "escalation",
  reason: "Should totals include tax?",
  created_at: "2026-11-26T14:05:00+00:00",
  link: "https://github.com/acme/shop/issues/7",
};

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

function column(feature: string, status: string) {
  return within(screen.getByRole("region", { name: `${feature} ${status}` }));
}

async function open(page: string): Promise<void> {
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: page }));
}

test("FT-13.5 board puts tickets in their status column and shows dependencies", async () => {
  serveApi({ current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/board": board("review") } });
  await open("Board");
  await screen.findByRole("region", { name: "cart review" });
  expect(column("cart", "review").getByText("TKT-1")).toBeInTheDocument();
  expect(column("cart", "todo").getByText("TKT-2")).toBeInTheDocument();
  expect(within(screen.getByTestId("ticket-TKT-2")).getByText("depends on TKT-1")).toBeInTheDocument();
  expect(within(screen.getByTestId("ticket-TKT-1")).queryByText(/depends on/)).toBeNull();
});

test("FT-13.6 inbox lists an escalated ticket with its ask and issue link", async () => {
  serveApi({ current: { "/api/inbox": [ESCALATION] } });
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  expect(entry.getByText("Should totals include tax?")).toBeInTheDocument();
  expect(entry.getByRole("link", { name: "Open issue" })).toHaveAttribute("href", ESCALATION.link);
});

test("FT-13.7 Continue sends the typed response and refetches the inbox", async () => {
  const routes = {
    current: {
      "/api/inbox": [ESCALATION],
      "POST /api/inbox/inc-1/continue": { status: 200, body: { run: null, reason: "resolving" } },
    } as Record<string, unknown>,
  };
  const calls = serveApi(routes);
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  const button = entry.getByRole("button", { name: "Continue" });
  expect(button).toBeDisabled();
  fireEvent.change(entry.getByLabelText("Response"), { target: { value: "Yes, include tax" } });
  routes.current["/api/inbox"] = [];
  fireEvent.click(button);
  expect(await screen.findByText("Nothing waiting for you.")).toBeInTheDocument();
  const post = calls.find((c) => c.method === "POST");
  expect(post).toEqual({
    method: "POST",
    path: "/api/inbox/inc-1/continue",
    body: { response: "Yes, include tax" },
  });
});

test("FT-13.8 Continue shows the engine's error message", async () => {
  serveApi({
    current: {
      "/api/inbox": [{ ...ESCALATION, kind: "budget", reason: "ticket budget reached", link: null }],
      "POST /api/inbox/inc-1/continue": {
        status: 404,
        body: { error: { code: "hold_not_found", message: "item inc-1 not found" } },
      },
    },
  });
  await open("Inbox");
  const entry = within(await screen.findByTestId("inbox-TKT-1"));
  expect(entry.queryByLabelText("Response")).toBeNull();
  fireEvent.click(entry.getByRole("button", { name: "Continue" }));
  expect(await entry.findByText("item inc-1 not found")).toBeInTheDocument();
});

test("FT-13.9 run.finished event refetches the board without reload", async () => {
  const routes = {
    current: { "/api/projects": [{ name: "shop" }], "/api/projects/shop/board": board("todo") } as Record<
      string,
      unknown
    >,
  };
  serveApi(routes);
  await open("Board");
  await screen.findByRole("region", { name: "cart todo" });
  await vi.waitFor(() => expect(column("cart", "todo").getByText("TKT-1")).toBeInTheDocument());
  routes.current["/api/projects/shop/board"] = board("planned");
  act(() => FakeEventSource.last?.emit("run.finished"));
  await vi.waitFor(() => expect(column("cart", "planned").getByText("TKT-1")).toBeInTheDocument());
});

test("FT-13.10 board without projects says so", async () => {
  serveApi({ current: { "/api/projects": [] } });
  await open("Board");
  expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
});
