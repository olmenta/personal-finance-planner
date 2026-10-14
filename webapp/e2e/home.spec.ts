import { expect, test } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* redesign-home-navigation, task 5.3 — on 14 October 2026:
   1. five destinations on desktop and on mobile;
   2. "Needs organizing" with reasons, and a breakdown that adds up;
   3. Future coverage unknown without income;
   4. /upcoming and /coach redirect;
   5. What you owe is reached from Accounts. */

test.describe.configure({ mode: "serial" });

let api: Api;
let ids: Record<string, string>;

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  api = new Api(await playwright.request.newContext({ baseURL }));
  ids = await api.categories();
  await api.income(300000, "2026-10-01");
  await api.openMonth("2026-10");
  await api.expense(ids["Ocio"], 4500, "2026-10-08"); // nothing assigned: Ocio goes over
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

test("the sidebar has the five destinations", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator(".app-sidebar nav");
  for (const name of ["Home", "Budget", "Transactions", "Future", "Accounts"]) {
    await expect(nav.getByRole("link", { name, exact: true })).toBeVisible();
  }
  await expect(nav.getByRole("link", { name: "Goals" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Coach" })).toHaveCount(0);
});

test("Home says the month needs organizing, and why", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("coach-line")).toContainText("1 category needs money before I can give you a reliable amount to spend");
  await expect(page.getByTestId("left-to-spend")).toContainText("Needs organizing");
  await expect(page.getByTestId("reasons")).toContainText(`Ocio ${eur(4500)}`);
  await page.getByRole("button", { name: "View exact breakdown" }).click();
  await expect(page.getByTestId("breakdown")).toContainText(`left to spend -${eur(4500)}`.replace("--", "-"));
});

test("Future coverage is unknown without expected income", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("future-widget")).toContainText("Coverage unknown");
  await expect(page.getByTestId("future-widget").getByRole("button", { name: "Add income" })).toBeVisible();
});

test("old links redirect", async ({ page }) => {
  await page.goto("/upcoming?month=2027-03");
  await expect(page).toHaveURL(/\/future\?month=2027-03$/);
  await page.goto("/coach");
  await expect(page).toHaveURL(/\/$/);
});

test("What you owe is reached from Accounts", async ({ page }) => {
  await page.goto("/accounts");
  await expect(page.getByTestId("debts-card")).toContainText("Nothing owed");
  await page.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/debts$/);
  await expect(page.locator(".app-sidebar nav").getByRole("link", { name: "Accounts", exact: true }))
    .toHaveAttribute("aria-current", "page");
});

test("mobile shows the five destinations and Settings", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const bar = page.getByRole("navigation", { name: "Main" });
  for (const name of ["Home", "Budget", "Transactions", "Future", "Accounts"]) {
    await expect(bar.getByRole("link", { name, exact: true })).toBeVisible();
  }
  await expect(bar.getByRole("button", { name: "Add transaction" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
});
