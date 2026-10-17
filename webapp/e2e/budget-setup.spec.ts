import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-budget-setup, task 8.3 — on 14 October 2026, coach on fake:e2e:
   1. a new category offers the similar one → "Use Mascotas" → the expense
      preview → confirm;
   2. creating a category in a picked group → the expense → Budget shows it;
   3. "New group…";
   4. a three-category budget in one confirmation;
   5. a cash expense lands in Efectivo. */

test.describe.configure({ mode: "serial" });

let api: Api;
let ids: Record<string, string>;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
  await api.createCategory("Mascotas", await api.groupId("Estilo de vida"));
  ids = await api.categories();
  await api.income(300000, "2026-10-01");
  await api.openMonth("2026-10");
  await api.expense(ids["Supermercado"], 3120, "2026-10-02", "Mercadona");
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

const choice = (page: Page) => page.getByTestId("category-choice").last();
const preview = (page: Page, text: string) => page.getByTestId("action-preview").filter({ hasText: text }).last();
const result = (page: Page, text: string) => page.getByTestId("action-result").filter({ hasText: text }).first();

test("a similar category is offered and used", async ({ page }) => {
  await say(page, "gasté 15 en el veterinario");
  await expect(choice(page)).toContainText("No category for “Veterinario” yet");
  await choice(page).getByRole("button", { name: "Use Mascotas · Estilo de vida" }).click();
  await expect(choice(page)).toContainText("Using Mascotas");
  const expense = preview(page, `Record ${eur(1500)} at Veterinario in Mascotas`);
  await expense.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Record ${eur(1500)} at Veterinario in Mascotas`)).toBeVisible();
});

test("a new category in a picked group, then the expense", async ({ page }) => {
  await say(page, "gasté 40 en el fisioterapeuta");
  await choice(page).getByRole("combobox", { name: "Group for the new category" }).click();
  await page.getByRole("option", { name: /^Estilo de vida/ }).click();
  await choice(page).getByRole("button", { name: "Create category" }).click();
  await expect(page.getByTestId("category-choice").filter({ hasText: "Created Fisioterapeuta in Estilo de vida" })).toBeVisible();
  const expense = preview(page, `Record ${eur(4000)} at Fisioterapeuta in Fisioterapeuta`);
  await expense.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Record ${eur(4000)}`)).toBeVisible();

  await page.goto("/budgets");
  await expect(page.getByTestId("category-row-Fisioterapeuta")).toBeVisible();
});

test("a new category in a new group", async ({ page }) => {
  await say(page, "gasté 30 en el colegio");
  await choice(page).getByRole("combobox", { name: "Group for the new category" }).click();
  await page.getByRole("option", { name: "New group…" }).click();
  await choice(page).getByLabel("New group name").fill("Hijos");
  await choice(page).getByRole("button", { name: "Create category" }).click();
  await expect(page.getByTestId("category-choice").filter({ hasText: "Created Colegio in a new group" })).toBeVisible();
  await expect(preview(page, `Record ${eur(3000)} at Colegio in Colegio`)).toBeVisible();
});

test("a budget of three categories is one confirmation", async ({ page }) => {
  await say(page, "pon 300 en el súper, 80 en gasolina y 50 en ocio");
  const budget = preview(page, "Set 3 categories");
  await expect(budget).toContainText(`Supermercado ${eur(30000)}, Gasolina ${eur(8000)}, Ocio ${eur(5000)}`);
  await expect(budget).toContainText("Supermercado: assigned");
  await budget.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, "Done: Set 3 categories")).toBeVisible();

  await page.goto("/budgets");
  await expect(page.getByTestId("category-row-Gasolina")).toContainText(eur(8000));
});

test("a cash expense lands in Efectivo", async ({ page }) => {
  await say(page, "pagué 12 en efectivo en Mercadona");
  const expense = preview(page, `Record ${eur(1200)} at Mercadona in Supermercado`);
  await expect(expense).toContainText("Efectivo");
  await expense.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Record ${eur(1200)} at Mercadona`)).toBeVisible();
});
