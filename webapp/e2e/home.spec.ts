import { expect, test } from "@playwright/test";
import { Api, euroCents as eur, pinClock, resetDb } from "./support/app";

/* redesign-home-navigation 5.3 and coach-conversation-actions 9.3 — on
   14 October 2026:
   1. five destinations, Settings and the user on desktop; no upsell;
   2. Home is the conversation: header, History, composer;
   3. the snapshot message says "Needs organizing" and why, and "View how
      it's split" shows a breakdown that adds up;
   4. Future coverage unknown without income;
   5. /upcoming and /coach redirect;
   6. What you owe is reached from Accounts;
   7. mobile shows the five destinations and Settings. */

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
  const sidebar = page.locator(".app-sidebar");
  await expect(sidebar.getByRole("link", { name: "Settings", exact: true })).toBeVisible();
  // The e2e suite runs without Auth0, as the development user (auth0-users).
  await expect(sidebar.getByTestId("sidebar-user")).toContainText("Development user");
  await expect(sidebar).not.toContainText("Maya Ortiz");
  await expect(sidebar).not.toContainText("Olmenta Pro");
});

test("Home is the conversation with Olmenta", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();
  await expect(page.getByText("Your conversation with Olmenta")).toBeVisible();
  await expect(page.getByTestId("history-button")).toBeVisible();
  await expect(page.getByPlaceholder("Ask or record an expense…")).toBeVisible();
  await expect(page.getByText("Your history is kept")).toBeVisible();
  await expect(page.getByTestId("snapshot-message")).toContainText("I've updated your month.");
});

test("Home says the month needs organizing, and why", async ({ page }) => {
  await page.goto("/");
  const line = page.getByTestId("coach-line");
  await expect(line).toContainText("1 category needs money before I can give you a reliable amount to spend");
  await expect(line.getByTestId("reasons")).toContainText(`Ocio ${eur(4500)}`);
  await page.getByRole("button", { name: "View how it's split" }).click();
  await expect(page.getByTestId("left-to-spend")).toContainText("Needs organizing");
  await expect(page.getByTestId("breakdown")).toContainText(`left to spend -${eur(4500)}`.replace("--", "-"));
});

test("Future coverage is unknown without expected income", async ({ page }) => {
  await page.goto("/");
  const future = page.getByTestId("future-line");
  await expect(future).toContainText("Coverage unknown");
  await expect(future.getByRole("link", { name: "Add income" })).toBeVisible();
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
