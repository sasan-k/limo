import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-14.15 prompts page shows build's prompt and history in light and dark with AA contrast", async ({
  page,
}) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Prompts" }).click();
    await expect(page.getByLabel("Content")).toHaveValue(/name: factory-build/);
    await expect(page.getByRole("region", { name: "history" }).locator("li").first()).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
