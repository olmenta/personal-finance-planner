import { expect, test, type Locator, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";
import { E2E_MONTH } from "./support/constants";

/* category-targets-and-annual-plan, task 8.2 — the manual verification as a
   scripted walk-through on 14 October 2026:
   1. set up the user's real payments through the editor;
   2. the dashboard's October split adds up to the money in the accounts;
   3. Upcoming payments shows the year's gap;
   4. a new month drafts the computed amounts.
   Steps share one database and run in order. */

test.describe.configure({ mode: "serial" });

let api: Api;
let ids: Record<string, string>;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  const request = await playwright.request.newContext({ baseURL });
  api = new Api(request);
  const group = await api.firstGroupId();
  for (const name of ["Colegio Tomi", "Seguro coche", "Agua", "Manameli"]) {
    await api.createCategory(name, group);
  }
  ids = await api.categories();
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

/* ---- helpers ------------------------------------------------------------ */

interface Payment {
  name: string;
  amount: string;
  /** Label in "How it's paid"; omitted = "Every month". */
  pattern?: string;
  /** Once a year: month name. */
  month?: string;
  /** Every N months: "3 months" and the next payment's month. */
  every?: string;
  next?: string;
  /** One payment on a date: its month. */
  when?: string;
  day?: string;
}

const row = (page: Page, category: string) => page.getByTestId(`category-row-${category}`);

async function openEditor(page: Page, category: string): Promise<Locator> {
  const r = row(page, category);
  await r.getByRole("button", { name: `Expand ${category}` }).click();
  await r.getByRole("button", { name: /^(Set up|Edit) payments$/ }).click();
  const dialog = page.getByRole("dialog", { name: `Payments · ${category}` });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function pick(page: Page, dialog: Locator, label: string, option: string) {
  // Radix renders a hidden native <select> under the same label; target the trigger.
  await dialog.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function addPayment(page: Page, dialog: Locator, p: Payment) {
  // The list's "Add payment" starts a fresh draft; the form's one submits it.
  await dialog.getByRole("button", { name: "Add payment" }).first().click();
  const form = dialog.locator("form");
  await form.getByLabel("Name").fill(p.name);
  if (p.pattern) await pick(page, form, "How it's paid", p.pattern);
  await form.getByLabel("Amount of each payment").fill(p.amount);
  if (p.month) await pick(page, form, "Month", p.month);
  if (p.every) await pick(page, form, "Every", p.every);
  if (p.next) await pick(page, form, "Next payment", p.next);
  if (p.when) await pick(page, form, "When", p.when);
  if (p.day) await form.getByLabel("Day of the month (optional)").fill(p.day);
  await form.getByRole("button", { name: "Add payment" }).click();
  // Saved: the form switches to editing the new payment.
  await expect(form.getByRole("button", { name: "Save payment" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: new RegExp(`^${p.name}`) })).toBeVisible();
}

async function setUpPayments(page: Page, category: string, payments: Payment[]): Promise<Locator> {
  const dialog = await openEditor(page, category);
  for (const p of payments) await addPayment(page, dialog, p);
  return dialog;
}

async function closeEditor(page: Page, dialog: Locator) {
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
}

/** "1.615,79 €" → 161579 */
function cents(text: string): number {
  const n = text.replace(/[^\d,-]/g, "").replace(",", ".");
  return Math.round(Number(n) * 100);
}

/** A dashboard section header: its title and total. */
const section = (page: Page, title: string) => page.getByText(title, { exact: true }).locator("..");

/* ---- 1. payments through the editor ----------------------------------------- */

test("sets up the real payments through the editor", async ({ page }) => {
  await page.goto("/budgets");
  await expect(row(page, "Colegio Tomi")).toBeVisible();

  // Colegio: nothing saved yet, so October needs the catch-up amount.
  const colegio = await setUpPayments(page, "Colegio Tomi", [
    // "Some months" preselects September–June, the school year.
    { name: "Cuota del colegio", amount: "632,00", pattern: "Some months", day: "5" },
    { name: "Libros", amount: "228,00", pattern: "Once a year", month: "September", day: "10" },
    { name: "Seguro AMPA", amount: "60,00", pattern: "Once a year", month: "October", day: "20" },
    { name: "Reconfirmación", amount: "387,00", pattern: "Once a year", month: "February", day: "15" },
  ]);
  // The amount cards come before the chart legend, which repeats the labels.
  const card = (label: string) => colegio.getByText(label, { exact: true }).first().locator("..");
  await expect(card("Normal amount")).toContainText(eur(58292));
  await expect(card("To be on time")).toContainText(eur(72140));
  await expect(colegio.getByText(`${eur(72140)}/month`)).toBeVisible();
  await closeEditor(page, colegio);

  await closeEditor(page, await setUpPayments(page, "Alquiler", [{ name: "Alquiler", amount: "952,00", day: "1" }]));
  await closeEditor(
    page,
    await setUpPayments(page, "Seguro coche", [
      { name: "Seguro del coche", amount: "500,00", pattern: "Once a year", month: "March" },
    ]),
  );
  await closeEditor(
    page,
    await setUpPayments(page, "Agua", [
      { name: "Agua", amount: "120,00", pattern: "Every N months", every: "3 months", next: "November 2026", day: "8" },
    ]),
  );
  await closeEditor(
    page,
    await setUpPayments(page, "Manameli", [
      { name: "Última cuota", amount: "1000,00", pattern: "One payment on a date", when: "October 2026", day: "15" },
    ]),
  );
  await closeEditor(
    page,
    await setUpPayments(page, "Suscripciones", [
      { name: "Streaming", amount: "9,99", day: "1" },
      { name: "Nube", amount: "30,22", day: "1" },
    ]),
  );

  // Every category with payments is assigned its computed amount, read-only.
  for (const [category, amount] of [
    ["Colegio Tomi", 72140],
    ["Alquiler", 95200],
    ["Manameli", 100000],
    ["Suscripciones", 4021],
  ] as const) {
    await expect(row(page, category)).toContainText("From your payments");
    await expect(row(page, category)).toContainText(eur(amount));
  }
  await expect(row(page, "Colegio Tomi")).toContainText(`normal ${eur(58292)}`);
  await expect(row(page, "Colegio Tomi")).toContainText(`to be on time ${eur(72140)}`);
});

/* ---- 2. the October split ---------------------------------------------------- */

test("the dashboard splits October and the accounts check holds", async ({ page }) => {
  await api.assign(E2E_MONTH, ids["Supermercado"], 40000);
  await api.income(470000, "2026-10-01");
  await api.expense(ids["Alquiler"], 95200, "2026-10-01");
  await api.expense(ids["Suscripciones"], 999, "2026-10-01");
  await api.expense(ids["Suscripciones"], 3022, "2026-10-01");
  await api.expense(ids["Colegio Tomi"], 63200, "2026-10-05");
  await api.expense(ids["Supermercado"], 12345, "2026-10-10");

  await page.goto("/");
  await expect(page.getByText("October 2026 · what to solve now")).toBeVisible();

  // Rent, subscriptions and the school fee are paid; plus the supermarket.
  await expect(section(page, "Already paid this month")).toContainText(eur(95200 + 4021 + 63200 + 12345));

  // Manameli (day 15) and the AMPA insurance (day 20) are pending, both set aside.
  const toPay = section(page, "Still to pay this month");
  await expect(toPay).toContainText(eur(106000));
  const pending = toPay.locator("..");
  for (const name of ["Manameli · Última cuota", "Colegio Tomi · Seguro AMPA"]) {
    const line = pending.getByText(name, { exact: true }).locator("../..");
    await expect(line).toContainText("set aside");
  }

  await expect(section(page, "Left to spend")).toContainText(eur(40000 - 12345));

  // In your accounts = income − spending; the split on the line adds up to it.
  const accountsCents = 470000 - 95200 - 4021 - 63200 - 12345;
  const check = page.getByText(/^In your accounts:/);
  await expect(check).toContainText(`In your accounts: ${eur(accountsCents)} = to pay ${eur(106000)}`);
  await expect(check).toContainText(`to spend ${eur(27655)}`);
  const text = (await check.textContent()) ?? "";
  const saved = cents(/saved ([^+]+)\+/.exec(text)?.[1] ?? "");
  const unassigned = cents(/unassigned (.+)$/.exec(text)?.[1] ?? "");
  expect(106000 + 27655 + saved + unassigned).toBe(accountsCents);
});

/* ---- 3. the year's gap -------------------------------------------------------- */

test("Upcoming payments shows the year's gap", async ({ page }) => {
  await page.goto("/upcoming");
  await page.getByLabel("Fixed monthly income").fill("2100,00");
  await page.getByRole("button", { name: "Save income" }).click();

  // Oct 2026–Sep 2027: rent 11.424 + school 6.995 + car 500 + water 480 +
  // Manameli 1.000 + subscriptions 482,52 = 20.881,52 €; day-to-day 400 × 12.
  const costs = 2088152 + 480000;
  const gap = 12 * 210000 - costs;
  await expect(page.getByText("Planned costs").locator("..")).toContainText(eur(costs));
  const short = page.getByText("Short", { exact: true }).locator("..");
  await expect(short).toContainText(eur(-gap));
  await expect(short).toContainText(`${eur(Math.round(-gap / 12))} a month`);
});

/* ---- 4. a new month drafts the computed amounts ---------------------------- */

test("a new month drafts the computed amounts", async ({ page }) => {
  await page.goto("/budgets");
  await page.getByRole("combobox").filter({ hasText: "October 2026" }).click();
  await page.getByRole("option", { name: "November 2026" }).click();

  for (const [category, amount] of [
    ["Alquiler", 95200],
    ["Suscripciones", 4021],
  ] as const) {
    await expect(row(page, category)).toContainText("From your payments");
    await expect(row(page, category)).toContainText(eur(amount));
  }
});

/* ---- month-overview spec: a short payment is visible without digging ------- */

test("a pending payment that lost its money shows how short it is", async ({ page }) => {
  await api.move(E2E_MONTH, ids["Manameli"], ids["Supermercado"], 50200);

  await page.goto("/");
  const line = page.getByText("Manameli · Última cuota", { exact: true }).locator("../..");
  await expect(line).toContainText(`short ${eur(50200)}`);
  await expect(section(page, "Left to spend")).toContainText(eur(27655 + 50200));
  await expect(page.getByText(/^In your accounts:/)).toContainText(eur(470000 - 95200 - 4021 - 63200 - 12345));
});
