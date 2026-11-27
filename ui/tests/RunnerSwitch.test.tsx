import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { renderApp, serveApi } from "./harness";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

test("FT-16.8 the switch shows off, and a click turns the runner on", async () => {
  const calls = serveApi({
    current: {
      "/api/runner": { enabled: false },
      "PUT /api/runner": { status: 200, body: { enabled: true } },
    },
  });
  renderApp();
  const button = await screen.findByRole("button", { name: "Runner off" });
  await vi.waitFor(() => expect(button).toBeEnabled());
  expect(button).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(button);
  const on = await screen.findByRole("button", { name: "Runner on" });
  expect(on).toHaveAttribute("aria-pressed", "true");
  expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ enabled: true });
});

test("FT-16.9 a failed switch shows the engine's message and stays off", async () => {
  serveApi({
    current: {
      "/api/runner": { enabled: false },
      "PUT /api/runner": {
        status: 500,
        body: { error: { code: "internal", message: "runner unavailable" } },
      },
    },
  });
  renderApp();
  const button = await screen.findByRole("button", { name: "Runner off" });
  await vi.waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByText("runner unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Runner off" })).toBeInTheDocument();
});
