import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-debts-setup, task 7.3 — on 14 October 2026, coach on fake:e2e:
   1. "la Visa debe 634,62 y puedo pagar 200 al mes" → debt preview →
      confirm → What you owe lists it;
   2. "¿y si pongo 100 más al mes?" → preview with the debt-free month →
      cancel → the extra is unchanged;
   3. "Talk it through with your coach" fills the composer. */

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  const api = new Api(await playwright.request.newContext({ baseURL }));
  await api.createAccount({ name: "Banco", type: "bank", opening_balance_cents: 100000 });
  await api.createAccount({ name: "Visa", type: "credit", opening_balance_cents: -63462 });
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

test("a card debt from a sentence", async ({ page }) => {
  await say(page, "la Visa debe 634,62 y puedo pagar 200 al mes");
  const debt = preview(page, "Add debt: Visa");
  await expect(debt.getByTestId("debt-preview")).toContainText(`${eur(20000)} a month`);
  await expect(debt.getByTestId("debt-free")).toContainText("no debts");
  await expect(debt).toContainText("Paid first");
  await debt.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByTestId("action-result").filter({ hasText: "Done: Add debt: Visa" }).first()).toBeVisible();

  await page.goto("/debts");
  await expect(page.getByText("Visa", { exact: true })).toBeVisible();
});

test("a what-if extra changes nothing until confirmed", async ({ page }) => {
  await say(page, "¿y si pongo 100 más al mes?");
  const extra = preview(page, "Pay 100,00 € extra a month on debts");
  await expect(extra.getByTestId("debt-free")).toBeVisible();
  await expect(extra).toContainText("It goes first to Visa");
  await expect(extra.getByTestId("cushion-note")).toContainText("so the next surprise doesn't end up on the card");
  await extra.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByTestId("action-preview").filter({ hasText: "Cancelled" }).last()).toBeVisible();

  const debts = await (await page.request.get("/api/debts")).json();
  expect(debts.extra_monthly_cents).toBe(0);
});

test("from What you owe to the conversation", async ({ page }) => {
  await page.goto("/debts");
  await page.getByTestId("talk-to-coach").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByPlaceholder("Ask or record an expense…")).toHaveValue("Quiero ordenar mis deudas");
  await expect(page.getByTestId("user-message").filter({ hasText: "Quiero ordenar mis deudas" })).toHaveCount(0);
});
