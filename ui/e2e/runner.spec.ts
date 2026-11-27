import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-16.10 the runner switch starts off, in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    const runner = page.getByRole("button", { name: "Runner off" });
    await expect(runner).toBeEnabled();
    await expect(runner).toHaveAttribute("aria-pressed", "false");
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
