import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";

import type { AgentCard } from "@/api/types";
import { App } from "@/App";

/** Stand-in for the browser EventSource; `emit` delivers one SSE event to listeners. */
export class FakeEventSource {
  static last: FakeEventSource | null = null;
  readonly url: string;
  private listeners = new Map<string, Array<() => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  addEventListener(type: string, listener: () => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {}

  emit(type: string): void {
    for (const listener of this.listeners.get(type) ?? []) listener();
  }
}

/** Engine stub: GET /api/agent-cards answers with whatever `cards.current` holds at call time. */
export function serveCards(cards: { current: AgentCard[] }, status = 200): void {
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(cards.current), { status })),
  );
}

export type ApiCall = { method: string; path: string; body: unknown };

/** Engine stub for any GET path in `routes.current` (else 404); records every call in the returned list.
 * A route value `{ status, body }` under key `"POST <path>"` answers that POST. */
export function serveApi(routes: { current: Record<string, unknown> }): ApiCall[] {
  const calls: ApiCall[] = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const key = method === "GET" ? path : `${method} ${path}`;
      if (!(key in routes.current)) return new Response("{}", { status: 404 });
      const value = routes.current[key];
      if (method === "GET") return new Response(JSON.stringify(value), { status: 200 });
      const reply = value as { status: number; body: unknown };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return calls;
}

/** Renders the whole app with a fresh query client (no retries). */
export function renderApp(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

export function card(overrides: Partial<AgentCard> = {}): AgentCard {
  return {
    agent: "build",
    model: "claude-haiku-5-5",
    state: "idle",
    project: "shop",
    feature: "cart",
    ticket: "TKT-1",
    cost: "0.400000",
    last_run: {
      id: "r1",
      status: "succeeded",
      tokens: 52000,
      started_at: "2026-11-26T14:01:00+00:00",
      finished_at: "2026-11-26T14:05:00+00:00",
      duration_s: 240,
      tries: 1,
    },
    ...overrides,
  };
}
