import { expect, test } from "@playwright/test";

test("modular MCP v2 loads Graph through a fresh browser session", async ({ page }) => {
  const available = await page.request.get("/").then((response) => response.ok()).catch(() => false);
  test.skip(!available, "Companion-X dashboard is not running on :3000.");

  await page.goto("/");
  await page.getByTitle("Graph").click();
  await expect(page.getByText(/API 404: Tool/)).toHaveCount(0, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Select a workflow run" })).toBeVisible();
  await page.getByRole("button", { name: "Select a workflow run" }).click();
  await expect(page.getByText(/Runs unavailable/)).toHaveCount(0);
});
