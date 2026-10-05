import { expect, test, type Locator, type Page } from "@playwright/test";
import { pinClock, resetDb } from "./support/app";

/* uncategorized-and-category-combobox, task 6.3:
   1. typing in a long import review keeps up with the keyboard;
   2. a category created from one row's picker is offered in the next row;
   3. what's confirmed without a category shows up as "Uncategorized" on
      the budget, and "Categorize now" opens the review there.
   Steps share one database and run in order. No live LLM in e2e, so the
   import stages rows uncategorized and the review has nothing to suggest. */

test.describe.configure({ mode: "serial" });

const ROWS = 80;

function statementCsv(): Buffer {
  const lines = ["date,amount,description,category,balance"];
  for (let i = 0; i < ROWS; i++) {
    const day = String((i % 13) + 1).padStart(2, "0");
    lines.push(`${day}/10/2026,-${(i + 1).toFixed(2)},Compra tienda ${i + 1},,`);
  }
  return Buffer.from(lines.join("\n"), "utf8");
}

test.beforeAll(() => {
  resetDb();
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

async function openReview(page: Page): Promise<Locator> {
  await page.goto("/transactions");
  await page.getByRole("button", { name: /Import bank transactions|Resume review/ }).first().click();
  // By name: the category picker's popover is a dialog too.
  const dialog = page.getByRole("dialog", { name: /Import bank transactions|Review your import/ });
  if (await dialog.getByRole("radio", { name: /Custom CSV/ }).isVisible()) {
    await dialog.getByRole("radio", { name: /Custom CSV/ }).click();
    await dialog.locator('input[type="file"]').setInputFiles({
      name: "statement.csv",
      mimeType: "text/csv",
      buffer: statementCsv(),
    });
    await dialog.getByRole("button", { name: "Upload and review" }).click();
  }
  await expect(dialog.getByRole("heading", { name: "Review your import" })).toBeVisible();
  return dialog;
}

test("typing a note in a long review keeps up", async ({ page }) => {
  const dialog = await openReview(page);
  const notes = dialog.getByRole("textbox", { name: "Note" });
  await expect(notes).toHaveCount(ROWS);

  const note = notes.nth(40);
  const text = "Regalo de cumpleaños para Ana";
  await note.fill("");
  const started = Date.now();
  await note.pressSequentially(text);
  const elapsed = Date.now() - started;
  await expect(note).toHaveValue(text);
  // Only the edited row re-renders: a keystroke must not cost a full redraw
  // of 80 rows. Generous bound — the lagging version took several seconds.
  expect(elapsed).toBeLessThan(ROWS * 40);
});

test("a category created from one row is offered in the next", async ({ page }) => {
  const dialog = await openReview(page);
  const pickers = dialog.getByRole("button", { name: "Category" });

  await pickers.nth(0).click();
  await page.getByPlaceholder("Search or create…").fill("Mascotas");
  await page.getByRole("option", { name: "Create «Mascotas»" }).click();
  await expect(page.getByLabel("Category name")).toHaveValue("Mascotas");
  await page.getByRole("button", { name: "Create category" }).click();
  await expect(pickers.nth(0)).toHaveText(/Mascotas/);

  await pickers.nth(1).click();
  await page.getByPlaceholder("Search or create…").fill("masc");
  await expect(page.getByRole("option", { name: "Mascotas" })).toBeVisible();
  // An exact match offers no creation.
  await page.getByPlaceholder("Search or create…").fill("mascotas");
  await expect(page.getByRole("option", { name: /^Create/ })).toHaveCount(0);
  await page.getByRole("option", { name: "Mascotas" }).click();
  await expect(pickers.nth(1)).toHaveText(/Mascotas/);

  await dialog.getByRole("button", { name: "Confirm import" }).click();
  await expect(dialog).toBeHidden();
});

test("uncategorized spending shows on the budget", async ({ page }) => {
  await page.goto("/budgets");
  const block = page.getByRole("region", { name: "Uncategorized spending" });
  await expect(block).toBeVisible();
  // Two of the rows got "Mascotas"; the rest are still waiting.
  await expect(block).toContainText(`${ROWS - 2} movements`);

  await block.getByRole("button", { name: "Categorize now" }).click();
  // No live LLM in e2e: the review explains and points to manual categorizing.
  await expect(page.getByText("Nothing to suggest right now")).toBeVisible();
});
