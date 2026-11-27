import { defineConfig, devices } from "@playwright/test";

/** E2E: the real UI (vite) against the engine started with fakes (engine/tests/e2e_app.py). */
export default defineConfig({
  testDir: "e2e",
  use: { baseURL: "http://127.0.0.1:5174" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run python -m tests.e2e_app",
      cwd: "../engine",
      url: "http://127.0.0.1:8701/api/agent-cards",
      reuseExistingServer: false,
    },
    {
      command: "npx vite --port 5174 --strictPort --bypass-lock",
      url: "http://127.0.0.1:5174",
      env: { LIMO_API_URL: "http://127.0.0.1:8701" },
      reuseExistingServer: false,
    },
  ],
});
