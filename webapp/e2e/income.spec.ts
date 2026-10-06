import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* income-schedules, task 8.3 — on 14 October 2026:
   1. fourteen pagas set up in Settings → Income;
   2. June's extra pay shows in Upcoming payments;
   3. a lower salary reads "received · X € less" in the budget breakdown;
   4. unplanned income is linked with "This is…";
   5. a late income nudges from the dashboard and "Add it" clears it.
   Steps share one database and run in order. */

test.describe.configure({ mode: "serial" });

let api: Api;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

async function openBreakdown(page: Page) {
  await page.goto("/budgets");
  await page.getByRole("button", { name: "See where the money to assign comes from" }).click();
  const dialog = page.getByRole("dialog", { name: "Money to assign · October 2026" });
  await expect(dialog).toBeVisible();
  return dialog;
}

const occurrence = (page: Page, name: string) =>
  page.getByTestId("income-occurrence").filter({ hasText: name });

test("sets up fourteen pagas in Settings", async ({ page }) => {
  await page.goto("/settings");
  const form = page.getByRole("form", { name: "Income form" });
  await expect(page.getByText("Add your income to see if your plan fits.")).toBeVisible();
  await form.getByLabel("Name").fill("Nómina");
  await form.getByLabel("Payer").fill("Acme SL");
  await form.getByLabel("Net amount each time").fill("2000");
  await form.getByLabel("Day of the month (optional)").fill("27");
  await form.getByRole("button", { name: "14 payments a year" }).click();

  await expect(page.getByTestId("income-yearly")).toHaveText(eur(2800000));
  await expect(page.getByRole("button", { name: /^Paga extra/ })).toContainText("in Jun, Dec, day 27 · Acme SL");
});

test("June's extra pay shows in Upcoming payments", async ({ page }) => {
  await page.goto("/upcoming");
  const june = page.getByRole("button", { name: /June 2027/ });
  await expect(june).toContainText(`+${eur(400000)}`);
  await expect(page.getByRole("button", { name: /May 2027/ })).toContainText(`+${eur(200000)}`);
});

test("a lower salary shows the difference in the breakdown", async ({ page }) => {
  await api.income(195000, "2026-10-13", "ACME SL");
  const dialog = await openBreakdown(page);
  await expect(occurrence(page, "Nómina")).toContainText(`received · ${eur(5000)} less`);
  await expect(dialog).toContainText(`expected ${eur(200000)} · received ${eur(195000)}`);
});

test("unplanned income is linked with This is…", async ({ page }) => {
  await api.incomeSchedule({ name: "Alquiler piso", amount_cents: 90000, pattern: "monthly", day: 3 });
  await api.income(118000, "2026-10-03", "Inquilino Piso"); // too far from 900 €: unplanned
  const dialog = await openBreakdown(page);
  await expect(dialog).toContainText("Unplanned income");
  await dialog.getByRole("combobox", { name: "Link Inquilino Piso to an expected income" }).click();
  await page.getByRole("option", { name: `Alquiler piso · ${eur(90000)}` }).click();
  await expect(occurrence(page, "Alquiler piso")).toContainText(`received · ${eur(28000)} more`);
  await expect(dialog).not.toContainText("Unplanned income");
});

test("a late income nudges from the dashboard until it's added", async ({ page }) => {
  await api.incomeSchedule({ name: "Pensión", payer: "INSS", amount_cents: 70000, pattern: "monthly", day: 5 });
  await page.goto("/");
  const nudge = page.getByTestId("late-income-nudge");
  await expect(nudge).toContainText(`Your Pensión (${eur(70000)}) usually arrives on the 5th and isn't here yet`);

  await nudge.getByText("Add it").click();
  const dialog = page.getByRole("dialog", { name: "Add transaction" });
  await expect(dialog.getByLabel("Amount")).toHaveValue("700,00");
  await expect(dialog.getByLabel("Payer")).toHaveValue("INSS");
  await dialog.getByRole("button", { name: "Add income" }).click();

  await expect(nudge).toBeHidden();
});
