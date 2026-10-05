import path from "node:path";
import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { pinClock, resetDb } from "./support/app";

/* Real bank exports from test-assets/ through the real adapters, end to end:
   1. the BBVA export lands in the chosen account and its outgoing transfer
      to Sabadell is marked at review;
   2. the Sabadell export's matching incoming row is linked to that transfer
      instead of being imported twice;
   3. importing the same Sabadell statement again skips every row.
   No live LLM in e2e: rows stage uncategorized. Steps share one database
   and run in order. */

test.describe.configure({ mode: "serial" });

const ASSETS = path.resolve(__dirname, "../../test-assets");
const BBVA_EXPORT = path.join(ASSETS, "2026Y-10M-04D-21_29_29-Últimos movimientos.xlsx");
const SABADELL_EXPORT = path.join(ASSETS, "sabadell-abonos.xls");
// Same movements as SABADELL_EXPORT, exported again.
const SABADELL_AGAIN = path.join(ASSETS, "sabadell-agosto-sept.xls");

interface Txn {
  id: string;
  account_id: string;
  amount_cents: number;
  transfer_pair_id: string | null;
}

let request: APIRequestContext;
let bbva: string;
let sabadell: string;

async function createAccount(name: string): Promise<string> {
  const response = await request.post("/api/accounts", { data: { name, type: "bank" } });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).id;
}

async function transactionsIn(month: string, accountId: string): Promise<Txn[]> {
  const response = await request.get(`/api/transactions?month=${month}`);
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as Txn[]).filter((t) => t.account_id === accountId);
}

/** Upload a statement into an account and land on its review. */
async function uploadStatement(page: Page, account: string, bank: RegExp, file: string): Promise<Locator> {
  await page.goto("/transactions");
  await page.getByRole("button", { name: "Import bank transactions" }).click();
  const dialog = page.getByRole("dialog", { name: /Import bank transactions|Review your import/ });
  await dialog.getByRole("combobox", { name: "Import into" }).click();
  await page.getByRole("option", { name: account, exact: true }).click();
  await dialog.getByRole("radio", { name: bank }).click();
  await dialog.locator('input[type="file"]').setInputFiles(file);
  await dialog.getByRole("button", { name: "Upload and review" }).click();
  await expect(dialog.getByRole("heading", { name: "Review your import" })).toBeVisible();
  return dialog;
}

/** A review row by the start of its bank text and its amount cell. */
const reviewRow = (dialog: Locator, text: RegExp, amount: string) =>
  dialog.getByRole("group", { name: text }).filter({ hasText: amount }).first();

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  request = await playwright.request.newContext({ baseURL });
  bbva = await createAccount("BBVA");
  sabadell = await createAccount("Sabadell");
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

test("the BBVA export lands in its account and its transfer is marked", async ({ page }) => {
  const dialog = await uploadStatement(page, "BBVA", /BBVA - es/, BBVA_EXPORT);
  await expect(dialog).toContainText("178 transactions ready to import");

  const transfer = reviewRow(dialog, /^Transferencia realizada/, "−600,00 €");
  await transfer.getByRole("button", { name: "Category" }).click();
  await page.getByPlaceholder("Search or create…").fill("Sabadell");
  await page.getByRole("option", { name: "Transfer → Sabadell" }).click();
  await expect(transfer.getByRole("button", { name: "Category" })).toHaveText(/Transfer → Sabadell/);

  await dialog.getByRole("button", { name: "Confirm import" }).click();
  await expect(dialog).toBeHidden();

  // The −600,00 € is linked to a +600,00 € twin created in Sabadell.
  const out = (await transactionsIn("2026-09", bbva)).find((t) => t.amount_cents === -60000);
  expect(out?.transfer_pair_id).toBeTruthy();
  const twin = (await transactionsIn("2026-09", sabadell)).find(
    (t) => t.transfer_pair_id === out?.transfer_pair_id,
  );
  expect(twin?.amount_cents).toBe(60000);
});

test("the Sabadell side links to that transfer instead of duplicating it", async ({ page }) => {
  const dialog = await uploadStatement(page, "Sabadell", /Sabadell - es/, SABADELL_EXPORT);
  await expect(dialog).toContainText("17 transactions ready to import");

  const incoming = reviewRow(dialog, /^ABONO TRANSFERENCIA/, "+600,00 €");
  await expect(incoming).toContainText("Looks like the transfer from BBVA");
  await incoming.getByRole("button", { name: "Link them" }).click();
  await expect(incoming).toContainText("won't be added twice");

  await dialog.getByRole("button", { name: "Confirm import" }).click();
  await expect(dialog).toBeHidden();

  // Exactly one +600,00 € in Sabadell: the transfer's twin, adopted.
  const inSabadell = (await transactionsIn("2026-09", sabadell)).filter((t) => t.amount_cents === 60000);
  expect(inSabadell).toHaveLength(1);
  expect(inSabadell[0].transfer_pair_id).toBeTruthy();
});

test("importing the same Sabadell statement again skips every row", async ({ page }) => {
  const dialog = await uploadStatement(page, "Sabadell", /Sabadell - es/, SABADELL_AGAIN);
  await expect(dialog.getByText("These transactions are already in")).toBeVisible();
  await expect(dialog).toContainText("17 rows already imported — skipped");
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(dialog.getByRole("heading", { name: "Import bank transactions" })).toBeVisible();
});
