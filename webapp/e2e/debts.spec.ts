import { expect, test, type Locator, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* debt-paydown, task 7.3 — on 14 October 2026:
   1. a card debt with a plan from a target month, order and debt-free month;
   2. a loan and a personal debt with a date;
   3. the late-installment nudge on the dashboard;
   4. "Work on my debts" opens the editor from a row;
   5. a loan set up as a card is converted from the accounts screen.
   Steps share one database and run in order. */

test.describe.configure({ mode: "serial" });

let api: Api;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
  await api.createAccount({ name: "Sabadell - Visa", type: "credit", opening_balance_cents: -63462 });
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

async function openEditor(page: Page): Promise<Locator> {
  await page.goto("/debts");
  await page.getByTestId("work-on-debts").click();
  const dialog = page.getByRole("dialog", { name: "Add something you owe" });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function pick(page: Page, scope: Locator, label: string, option: string) {
  await scope.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

const row = (page: Page, name: string) => page.getByTestId(`debt-row-${name}`);

test("a card plan from a target month, with and without interest", async ({ page }) => {
  await page.goto("/debts");
  await expect(page.getByText("List what you owe")).toBeVisible();

  const dialog = await openEditor(page);
  await pick(page, dialog, "Which card?", "Sabadell - Visa");
  await expect(dialog).toContainText(`You owe ${eur(63462)}`);
  await dialog.getByRole("button", { name: "When do you want to be done?" }).click();
  await pick(page, dialog, "When do you want to be done?", "January 2027");
  await expect(dialog.getByTestId("card-plan-preview")).toHaveText(`That's ${eur(15866)} a month.`);

  await dialog.getByRole("button", { name: "% a month" }).click();
  await dialog.getByLabel("Interest").fill("1,5");
  await expect(dialog.getByTestId("card-plan-preview")).toHaveText(`That's ${eur(16465)} a month.`);
  await dialog.getByRole("button", { name: "Add to my plan" }).click();
  await expect(dialog).toBeHidden();

  await expect(page.getByTestId("debts-total")).toHaveText(eur(63462));
  await expect(page.getByTestId("debt-free")).toHaveText("Debt-free in January 2027 if you keep this plan");
  const visa = row(page, "Sabadell - Visa");
  await expect(visa).toContainText(`${eur(16465)} a month`);
  await expect(visa).toContainText("1,5 % a month");
  await expect(visa).toContainText("~9,52 €/month just for owing it");
});

test("a loan and a personal debt with a date join the plan in order", async ({ page }) => {
  let dialog = await openEditor(page);
  await dialog.getByRole("button", { name: "A loan with installments" }).click();
  await dialog.getByLabel("Name").fill("Ikea");
  await dialog.getByLabel("Each installment").fill("45");
  await dialog.getByLabel("Installments left").fill("10");
  await dialog.getByLabel("Day of the month (optional)").fill("5");
  await dialog.getByRole("button", { name: "Add to my plan" }).click();
  await expect(dialog).toBeHidden();

  dialog = await openEditor(page);
  await dialog.getByRole("button", { name: "Money I owe someone" }).click();
  await dialog.getByLabel("Name").fill("Jose y Ruby");
  await dialog.getByLabel("How much do you owe?").fill("2900");
  await dialog.getByRole("switch", { name: /need it back by a date/ }).click();
  await pick(page, dialog, "By when?", "March 2027");
  await dialog.getByRole("button", { name: "Add to my plan" }).click();
  await expect(dialog).toBeHidden();

  const names = page.locator("[data-testid^='debt-row-']");
  await expect(names).toHaveCount(3);
  await expect(names.nth(0)).toHaveAttribute("data-testid", "debt-row-Sabadell - Visa");
  await expect(row(page, "Ikea")).toContainText(`${eur(4500)} a month · 10 installments left`);
  await expect(row(page, "Jose y Ruby")).toContainText("due March 2027");
});

test("a late installment nudges from the dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("late-debt-nudge")).toContainText(
    "Your Ikea payment was due on the 5th and hasn't gone out yet",
  );
});

test("Work on my debts opens the plan of a row", async ({ page }) => {
  await page.goto("/debts");
  await row(page, "Ikea").getByRole("button", { name: "Work on my debts" }).click();
  const dialog = page.getByRole("dialog", { name: "Your plan · Ikea" });
  await expect(dialog.getByLabel("Installments left")).toHaveValue("10");
});

test("a loan set up as a card moves to What you owe", async ({ page }) => {
  await api.createAccount({ name: "Sabadell - Prestamo", type: "credit", opening_balance_cents: -970983, payment_day: 2 });
  await page.goto("/accounts");
  const account = page.getByText("Sabadell - Prestamo", { exact: true }).locator("xpath=ancestor::div[3]");
  await account.getByRole("button", { name: "Account actions" }).click();
  await page.getByRole("menuitem", { name: "This is a loan, not a card" }).click();
  const dialog = page.getByRole("dialog", { name: "This is a loan, not a card" });
  await dialog.getByLabel("Each installment").fill("290,17");
  await dialog.getByLabel("Installments left").fill("34");
  await dialog.getByRole("button", { name: "Move to What you owe" }).click();
  await expect(dialog).toBeHidden();

  await page.goto("/debts");
  await expect(row(page, "Sabadell - Prestamo")).toContainText(`${eur(29017)} a month · 34 installments left`);
});
