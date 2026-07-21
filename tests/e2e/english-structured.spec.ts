import { expect, test } from "@playwright/test";

test("English structured reading remains unrecorded until patient confirmation", async ({ page }) => {
  await page.goto("/patient");
  await expect(page.getByRole("heading", { name: /hello, tariro moyo/i })).toBeVisible();

  await page.getByRole("button", { name: "Record blood pressure" }).click();
  await page.getByLabel("Systolic").fill("132");
  await page.getByLabel("Diastolic").fill("84");
  await page.getByLabel("Measurement time").fill("2026-07-18T10:00");
  await page.getByLabel("I was resting when I measured").check();
  await page.getByRole("button", { name: "Review reading" }).click();

  await expect(page.getByText("Not yet recorded")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Confirm this reading" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm and save" }).click();

  await expect(page.getByText("Reading confirmed.")).toBeVisible();
  await expect(page.getByText("132 / 84")).toBeVisible();
});
