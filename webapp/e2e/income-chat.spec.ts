import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-income-setup, task 7.3 — on 14 October 2026, coach on fake:e2e:
   1. "cobro 2100 el día 28" → income preview → confirm → Home's Future is
      no longer "Coverage unknown";
   2. "mi sueldo sube a 2200" → confirm → undo. */

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  const api = new Api(await playwright.request.newContext({ baseURL }));
  await api.createAccount({ name: "Banco", type: "bank", opening_balance_cents: 100000 });
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

test("expected income from a sentence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("future-line")).toContainText("Coverage unknown");

  await say(page, "cobro 2100 el día 28");
  const income = preview(page, "Add income: Nómina");
  await expect(income.getByTestId("income-preview")).toContainText(`${eur(210000)} every month, day 28`);
  await expect(income.getByTestId("income-coverage")).toContainText("unknown");
  await expect(income).toContainText("To be assigned changes only when the money arrives");
  await expect(income.getByRole("button", { name: "Edit" })).toHaveCount(0);
  await income.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, "Done: Add income: Nómina")).toBeVisible();

  await page.goto("/");
  await expect(page.getByTestId("future-line")).not.toContainText("Coverage unknown");
});

test("expected income changed and undone", async ({ page }) => {
  await say(page, "mi sueldo sube a 2200");
  const change = preview(page, "Change income: Nómina");
  await expect(change).toContainText(`${eur(210000)} every month, day 28 → ${eur(220000)} every month, day 28`);
  await change.getByRole("button", { name: "Confirm" }).click();
  await result(page, "Done: Change income: Nómina").getByRole("button", { name: "Undo" }).click();
  await expect(result(page, "Undone: Change income: Nómina")).toBeVisible();
});
