import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-15.6 cost page renders empty totals in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Cost" }).click();
    await expect(page.getByTestId("cost-overall")).toHaveText("$0.00");
    await expect(
      page.getByRole("region", { name: "Per agent", exact: true }).getByText("No cost yet."),
    ).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
