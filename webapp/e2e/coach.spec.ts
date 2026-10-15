import { expect, test, type Page } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* coach-proposals, task 6.3 — on 14 October 2026, with three closed months:
   1. Restaurantes went over twice → the coach raises it, taking the money from Supermercado;
   2. "Not now" hides a proposal;
   3. Home shows the priority action and grouped suggestions, and no text input. */

test.describe.configure({ mode: "serial" });

let api: Api;
let ids: Record<string, string>;
const HISTORY = ["2026-07", "2026-08", "2026-09"];

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
  ids = await api.categories();
  await api.income(200000, "2026-07-01");
  const spending: Record<string, [number, number[]]> = {
    Restaurantes: [20000, [24000, 19000, 25000]], // over in July and September → raise
    Gasolina: [12000, [5500, 6200, 5800]], // always money left → lower
    Ocio: [10000, [4000, 3000, 3500]], // always money left → lower
    Supermercado: [40000, [10000, 12000, 11000]], // always money left → lower
  };
  for (const month of HISTORY) await api.openMonth(month);
  for (const [name, [assigned, spent]] of Object.entries(spending)) {
    for (const [i, month] of HISTORY.entries()) {
      await api.assign(month, ids[name], assigned);
      await api.expense(ids[name], spent[i], `${month}-10`);
    }
  }
  await api.income(100000, "2026-10-01"); // October money to assign
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

const proposal = (page: Page, title: string) =>
  page.getByTestId("coach-proposal").filter({ hasText: title });

test("Home shows one priority and the grouped suggestions on request", async ({ page }) => {
  await page.goto("/coach"); // the coach lives on Home now
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("priority-action")).toContainText("Restaurantes keeps going over");
  await page.getByRole("button", { name: /more suggestions?/ }).click();
  const adjustments = page.getByTestId("group-adjustments");
  await expect(adjustments).toContainText("Budget adjustments (3)");
  await adjustments.getByRole("button", { name: /Budget adjustments/ }).click();
  await expect(adjustments.getByTestId("coach-proposal")).toHaveCount(3);
  // The priority isn't repeated inside its group.
  await expect(adjustments).not.toContainText("Restaurantes keeps going over");
});

test("Restaurantes keeps going over and is raised in one tap", async ({ page }) => {
  await page.goto("/");
  const card = page.getByTestId("priority-action").getByTestId("coach-proposal");
  await expect(card).toContainText(`You usually spend about ${eur(23000)}. Raise it from ${eur(20000)}?`);
  await card.getByRole("button", { name: "Raise it" }).click();
  // Not enough left to assign in October: the card asks where the 30 € come from.
  await expect(card).toContainText(`There isn't ${eur(3000)} left to assign. Take it from:`);
  await card.getByRole("button", { name: /^Supermercado · / }).click();
  await expect(page.getByText("Restaurantes keeps going over")).toHaveCount(0);

  await page.goto("/budgets");
  await expect(page.getByTestId("category-row-Restaurantes")).toContainText(eur(23000));
});

test("Not now hides a proposal", async ({ page }) => {
  await page.goto("/");
  const openAdjustments = async () => {
    await page.getByRole("button", { name: /more suggestions?/ }).click();
    const group = page.getByTestId("group-adjustments");
    await group.getByRole("button", { name: /Budget adjustments/ }).click();
    return group;
  };
  let group = await openAdjustments();
  const card = group.getByTestId("coach-proposal").filter({ hasText: "Gasolina always has money left" });
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(card).toHaveCount(0);
  await page.reload();
  group = await openAdjustments();
  await expect(group.getByTestId("coach-proposal").filter({ hasText: "Gasolina" })).toHaveCount(0);
});
