import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* budget-spent-column 4.1 — on 14 October 2026, each budget row shows
   Assigned · Spent · Available:
   1. desktop: column labels and subtotals per group; Supermercado shows
      120 € assigned with 200 € carried from September, 138 € spent and
      182 € available;
   2. a card's payment category labels its middle amount "Paid";
   3. mobile: the labels are on each row, and the assigned amount still opens
      the numpad; the to-be-assigned bar shows its whole amount, without the
      "Confirm remaining" button the capsule under it repeats, and the capsule
      shows its whole message. */

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  const api = new Api(await playwright.request.newContext({ baseURL }));
  const ids = await api.categories();
  await api.income(300000, "2026-09-01");
  await api.openMonth("2026-09");
  await api.assign("2026-09", ids["Supermercado"], 30000);
  await api.expense(ids["Supermercado"], 10000, "2026-09-10");
  await api.openMonth("2026-10");
  await api.assign("2026-10", ids["Supermercado"], 12000);
  await api.expense(ids["Supermercado"], 13800, "2026-10-08");
  const bank = await api.createAccount({ name: "BBVA", type: "bank", opening_balance_cents: 100000 });
  const card = await api.createAccount({ name: "Visa", type: "credit", opening_balance_cents: -50000 });
  await api.transfer(bank, card, 15000, "2026-10-05");
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

const row = (page: Page, name: string) => page.getByTestId(`category-row-${name}`);

test("desktop rows read Assigned · Spent · Available, labeled per group", async ({ page }) => {
  await page.goto("/budgets");
  const supermercado = row(page, "Supermercado");
  await expect(page.getByTestId("spent-Supermercado")).toHaveText(eur(13800));
  await expect(page.getByTestId("carry-Supermercado")).toHaveText(`+${eur(20000)} from last month`);
  await expect(supermercado).toContainText(eur(18200));
  // The subtitle no longer repeats the spending.
  await expect(supermercado).not.toContainText(`Spent ${eur(13800)}`);

  const totals = page.getByTestId("group-totals-Comida");
  await expect(totals).toBeVisible();
  for (const label of ["Assigned", "Spent", "Available"]) {
    await expect(totals.getByText(label, { exact: true })).toBeVisible();
  }
  // Row labels are for mobile only.
  await expect(supermercado.getByText("Spent", { exact: true })).toBeHidden();
});

test("a card's payment category shows what was paid", async ({ page }) => {
  await page.goto("/budgets");
  await expect(page.getByTestId("spent-Pago Visa")).toHaveText(eur(15000));
  await expect(page.getByTestId("group-totals-Tarjetas de crédito").getByText("Paid", { exact: true })).toBeVisible();
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("each row carries its labels, and Assigned opens the numpad", async ({ page }) => {
    await page.goto("/budgets");
    const supermercado = row(page, "Supermercado");
    await expect(page.getByTestId("group-totals-Comida")).toBeHidden();

    const amount = page.locator(".tba-hero-amount");
    await expect(amount).toContainText("to assign");
    expect(await amount.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await expect(page.locator(".tba-hero").getByRole("button", { name: /Confirm/ })).toBeHidden();
    // The suggestions capsule keeps its whole message (it wraps instead of cutting).
    const capsule = page.getByTestId("coach-capsule-message");
    await expect(capsule).toHaveText(/suggested amounts? still pending$/);
    expect(await capsule.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)).toBe(true);

    for (const label of ["Assigned", "Spent", "Available"]) {
      await expect(supermercado.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(page.getByTestId("spent-Supermercado")).toHaveText(eur(13800));
    await supermercado.getByRole("button", { name: /^Assigned to Supermercado/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });
});
