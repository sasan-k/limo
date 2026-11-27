import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-13.11 board and inbox render in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    await page.getByRole("button", { name: "Board" }).click();
    await expect(page.getByRole("region", { name: "cart todo" }).getByText("TKT-2")).toBeVisible();
    await expect(page.getByTestId("ticket-TKT-2").getByText("depends on TKT-1")).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
    await page.getByRole("button", { name: "Inbox" }).click();
    await expect(page.getByText("Nothing waiting for you.")).toBeVisible();
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
