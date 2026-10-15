import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-conversation-actions, task 9.3 — on 14 October 2026, with the coach
   on the deterministic e2e fake (LLM_ROUTE_COACH_MODEL=fake:e2e):
   1. "how much to save" → the future payment card, and "Review adjustment"
      previews before anything changes;
   2. "gasté 40 en Mercadona" → preview → confirm → result → undo;
   3. cover two categories in one confirmation;
   4. a write between preview and confirm → "Needs updating";
   5. the draft survives leaving Home;
   6. History lists the actions;
   7. the coach being unavailable keeps the message and the rest of Home. */

test.describe.configure({ mode: "serial" });

let api: Api;
let ids: Record<string, string>;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
  ids = await api.categories();
  // 200 € set aside in September for a 600 € insurance due in February.
  await api.openMonth("2026-09");
  await api.assign("2026-09", ids["Suscripciones"], 20000);
  await api.schedule(ids["Suscripciones"], {
    name: "Seguro del coche", amount_cents: 60000, pattern: "annual", month: 2, day: 15,
  });
  await api.income(300000, "2026-10-01");
  await api.openMonth("2026-10");
  await api.assign("2026-10", ids["Supermercado"], 40000);
  // 30 € taken out of the insurance this month: 50 € left of the 80 € needed.
  await api.move("2026-10", ids["Suscripciones"], ids["Supermercado"], 3000);
  await api.expense(ids["Supermercado"], 3120, "2026-10-02", "Mercadona");
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

async function say(page: Page, text: string) {
  const box = page.getByPlaceholder("Ask or record an expense…");
  await box.fill(text);
  await box.press("Enter");
  await expect(page.getByTestId("user-message").filter({ hasText: text }).last()).toBeVisible();
}

const lastReply = (page: Page) => page.getByTestId("coach-message").last();
const result = (page: Page, text: string) => page.getByTestId("action-result").filter({ hasText: text }).first();

test("asking how much to save shows the payment card", async ({ page }) => {
  await page.goto("/");
  await say(page, "¿Cuánto tendría que guardar?");
  const card = page.getByTestId("future-payment").last();
  await expect(card).toContainText("Seguro del coche");
  await expect(card).toContainText("February 2027");
  await expect(card).toContainText("200 € saved of 600 €");
  await expect(card).toContainText("33%");
  await expect(card).toContainText("50 €/month");
  await expect(card).toContainText("80 €/month");
  await expect(card).toContainText("5 contributions of 80 €.");
  await expect(card).toContainText("Reviewing doesn't change your budget.");
  await expect(lastReply(page)).toContainText(`necesitas apartar ${eur(8000)} al mes`);

  await card.getByRole("button", { name: "Review adjustment" }).click();
  const preview = card.getByTestId("action-preview");
  await expect(preview).toContainText(`Move ${eur(3000)} from To be assigned to Suscripciones`);
  await expect(preview).toContainText("Money in accounts");
  await preview.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Move ${eur(3000)}`)).toBeVisible();
});

test("an expense is a preview until confirmed, and can be undone", async ({ page }) => {
  await page.goto("/");
  await say(page, "gasté 40 en Mercadona");
  await expect(lastReply(page).getByTestId("action-preview")).toContainText(`Record ${eur(4000)} at Mercadona in Supermercado`);
  const preview = page.getByTestId("action-preview").filter({ hasText: "at Mercadona" }).last();
  await expect(preview).toContainText("Review before confirming");

  await preview.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Record ${eur(4000)} at Mercadona`)).toBeVisible();

  await page.reload();
  await result(page, `Done: Record ${eur(4000)}`).getByRole("button", { name: "Undo" }).click();
  await expect(result(page, `Undone: Record ${eur(4000)}`)).toBeVisible();
});

test("covering two categories is one confirmation", async ({ page }) => {
  await api.expense(ids["Restaurantes"], 5000, "2026-10-05");
  await api.expense(ids["Gasolina"], 2500, "2026-10-06");
  await page.goto("/");
  await say(page, "cubre Restaurantes y Gasolina");
  await expect(lastReply(page).getByTestId("action-preview")).toContainText(`Move ${eur(7500)} to Restaurantes, Gasolina`);
  const preview = page.getByTestId("action-preview").filter({ hasText: "to Restaurantes, Gasolina" }).last();
  await expect(preview).toContainText("Restaurantes: available");
  await expect(preview).toContainText(eur(-5000));
  await expect(preview).toContainText("Money in accounts");
  await expect(preview).toContainText("unchanged");
  await preview.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Move ${eur(7500)}`)).toBeVisible();

  await page.goto("/budgets");
  await expect(page.getByTestId("category-row-Restaurantes")).toContainText(eur(5000));
  await expect(page.getByTestId("category-row-Gasolina")).toContainText(eur(2500));
});

test("a preview whose numbers changed says it needs updating", async ({ page }) => {
  await api.expense(ids["Ocio"], 1500, "2026-10-07");
  await page.goto("/");
  await say(page, "cubre Ocio");
  await expect(lastReply(page).getByTestId("action-preview")).toContainText(`Move ${eur(1500)} from To be assigned to Ocio`);
  const preview = page.getByTestId("action-preview").filter({ hasText: "to Ocio" }).last();
  await api.expense(ids["Ocio"], 500, "2026-10-08"); // written between preview and confirm
  await preview.getByRole("button", { name: "Confirm" }).click();
  const fresh = page.getByTestId("action-preview").filter({ has: page.getByTestId("needs-updating") });
  await expect(fresh).toHaveCount(1);
  await expect(fresh).toContainText(eur(-2000)); // Ocio's current available, before the move
  await fresh.getByRole("button", { name: "Confirm" }).click();
  await expect(result(page, `Done: Move ${eur(1500)}`)).toBeVisible();
});

test("the draft is kept after leaving Home", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Ask or record an expense…").fill("quería preguntarte por");
  await page.locator(".app-sidebar").getByRole("link", { name: "Budget", exact: true }).click();
  await expect(page).toHaveURL(/\/budgets$/);
  await page.locator(".app-sidebar").getByRole("link", { name: "Home", exact: true }).click();
  await expect(page.getByPlaceholder("Ask or record an expense…")).toHaveValue("quería preguntarte por");
});

test("History lists the actions, newest first", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("history-button").click();
  const items = page.getByTestId("history-sheet").getByTestId("history-item");
  await expect(items).toHaveCount(4);
  await expect(items.first()).toContainText(`Move ${eur(1500)} from To be assigned to Ocio`);
  await expect(items.filter({ hasText: `Undone: Record ${eur(4000)}` })).toHaveCount(1);
  await expect(items.first().getByRole("button", { name: "Undo" })).toBeVisible();
});

test("when the coach can't answer, the message and Home stay", async ({ page }) => {
  await page.goto("/");
  await say(page, "simula un fallo");
  await expect(page.getByTestId("coach-unavailable")).toContainText("The coach can't answer right now");
  await expect(page.getByTestId("snapshot-message")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("user-message").filter({ hasText: "simula un fallo" })).toHaveCount(1);
});
