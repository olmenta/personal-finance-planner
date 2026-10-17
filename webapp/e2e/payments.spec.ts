import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-payments-setup, task 7.3 — on 14 October 2026, coach on fake:e2e:
   1. "el alquiler son 850 al mes, el día 1" → payment preview → confirm →
      Budget shows Alquiler from its payments;
   2. "el alquiler sube a 900" → confirm → undo. */

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  const api = new Api(await playwright.request.newContext({ baseURL }));
  await api.income(300000, "2026-10-01");
  await api.openMonth("2026-10");
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

async function say(page: Page, text: string) {
  await page.goto("/");
  const box = page.getByPlaceholder("Ask or record an expense…");
  await box.fill(text);
  await box.press("Enter");
  await expect(page.getByTestId("user-message").filter({ hasText: text }).last()).toBeVisible();
}

const preview = (page: Page, text: string) => page.getByTestId("action-preview").filter({ hasText: text }).last();
const result = (page: Page, text: string) => page.getByTestId("action-result").filter({ hasText: text }).first();

test("rent set up from a sentence", async ({ page }) => {
  await say(page, "el alquiler son 850 al mes, el día 1");
  const rent = preview(page, "Add payment: Alquiler");
  await expect(rent.getByTestId("payment-preview")).toContainText(`${eur(85000)} every month, day 1`);
  await expect(rent).toContainText("Monthly amount");
  await expect(rent).toContainText("Next payment");
  await expect(rent.getByRole("button", { name: "Edit" })).toHaveCount(0);
  await rent.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, "Done: Add payment: Alquiler")).toBeVisible();

  await page.goto("/budgets");
  const row = page.getByTestId("category-row-Alquiler");
  await expect(row).toContainText("From your payments");
  await expect(row).toContainText(eur(85000));
});

test("a payment changed and undone", async ({ page }) => {
  await say(page, "el alquiler sube a 900");
  const change = preview(page, "Change payment: Alquiler");
  await expect(change).toContainText(`${eur(85000)} every month, day 1 → ${eur(90000)} every month, day 1`);
  await change.getByRole("button", { name: "Confirm" }).click();
  const done = result(page, "Done: Change payment: Alquiler");
  await done.getByRole("button", { name: "Undo" }).click();
  await expect(result(page, "Undone: Change payment: Alquiler")).toBeVisible();

  await page.goto("/budgets");
  await expect(page.getByTestId("category-row-Alquiler")).toContainText(eur(85000));
});
