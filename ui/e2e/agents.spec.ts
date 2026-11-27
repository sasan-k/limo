import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const AGENTS = ["architecture", "spec", "plan", "build", "verify", "close", "resolver"];

test("FT-12.9 agents page shows every agent card in light and dark with AA contrast", async ({ page }) => {
  await page.goto("/");
  for (const agent of AGENTS) await expect(page.getByTestId(`agent-card-${agent}`)).toBeVisible();
  for (const mode of ["light", "dark"]) {
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await expect(page.getByTestId("agent-card-build")).toBeVisible();
    await expect(page.locator("html")).toHaveClass(mode === "dark" ? /dark/ : /^(?!.*dark)/);
    const scan = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
    expect(scan.violations).toEqual([]);
  }
});

test("FT-12.10 theme toggle switches mode and the choice survives a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Light mode" })).toBeVisible();
});
