import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { PromptFile, PromptVersion } from "@/api/types";

import { renderApp, serveApi } from "./harness";

const A = "a".repeat(40);
const B = "b".repeat(40);
const C = "c".repeat(40);
const FILE = "/api/agents/build/file?path=SKILL.md";
const HISTORY = "/api/agents/build/history?path=SKILL.md";

function file(content: string, version: string, path = "SKILL.md"): PromptFile {
  return { agent: "build", path, content, version };
}

function version(v: string, message: string): PromptVersion {
  return { version: v, saved_at: "2026-11-26T14:05:00+00:00", message };
}

function routes(): { current: Record<string, unknown> } {
  return {
    current: {
      "/api/agents": [{ name: "plan" }, { name: "build" }],
      "/api/agents/build/files": ["SKILL.md", "templates/build-report.md"],
      [FILE]: file("# Build\n", B),
      [HISTORY]: [version(B, "prompt: build SKILL.md"), version(A, "init")],
    },
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

async function openPrompts(): Promise<void> {
  renderApp();
  fireEvent.click(screen.getByRole("button", { name: "Prompts" }));
  await screen.findByDisplayValue("# Build");
}

test("FT-14.11 saving the edited prompt sends content and base version, then shows the new version", async () => {
  const api = routes();
  api.current[`PUT ${FILE}`] = { status: 200, body: file("# Build\nAlways run the formatter last.\n", C) };
  const calls = serveApi(api);
  await openPrompts();
  const save = screen.getByRole("button", { name: "Save" });
  expect(save).toBeDisabled();
  const text = "# Build\nAlways run the formatter last.\n";
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: text } });
  api.current[FILE] = file(text, C);
  api.current[HISTORY] = [version(C, "prompt: build SKILL.md"), version(B, "prompt: build SKILL.md")];
  fireEvent.click(save);
  expect(await screen.findByText("ccccccc")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")).toEqual({
    method: "PUT",
    path: FILE,
    body: { content: text, base_version: B },
  });
});

test("FT-14.12 rolling back posts the chosen version and shows the restored content", async () => {
  const api = routes();
  api.current[`POST /api/agents/build/rollback?path=SKILL.md`] = { status: 200, body: file("# A\n", C) };
  const calls = serveApi(api);
  await openPrompts();
  await screen.findByRole("button", { name: "Roll back to aaaaaaa" });
  expect(screen.queryByRole("button", { name: "Roll back to bbbbbbb" })).toBeNull();
  api.current[FILE] = file("# A\n", C);
  fireEvent.click(screen.getByRole("button", { name: "Roll back to aaaaaaa" }));
  expect(await screen.findByDisplayValue("# A")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST")?.body).toEqual({ version: A });
});

test("FT-14.13 a stale save shows the engine's conflict message", async () => {
  const api = routes();
  const conflict = { error: { code: "version_conflict", message: "SKILL.md changed since bbbbbbb" } };
  api.current[`PUT ${FILE}`] = { status: 409, body: conflict };
  serveApi(api);
  await openPrompts();
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: "# Mine\n" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("SKILL.md changed since bbbbbbb")).toBeInTheDocument();
});

test("FT-14.14 choosing a reference file loads that file", async () => {
  const api = routes();
  const ref = "/api/agents/build/file?path=templates%2Fbuild-report.md";
  api.current[ref] = file("# Build report\n", A, "templates/build-report.md");
  api.current["/api/agents/build/history?path=templates%2Fbuild-report.md"] = [version(A, "init")];
  serveApi(api);
  await openPrompts();
  fireEvent.change(screen.getByLabelText("File"), { target: { value: "templates/build-report.md" } });
  expect(await screen.findByDisplayValue("# Build report")).toBeInTheDocument();
});
