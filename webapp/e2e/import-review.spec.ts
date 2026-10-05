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

/** Upload the statement (fresh) or resume the batch an earlier step left
    pending. Explicit, not "whatever the dialog shows": the dialog shows the
    bank picker until the pending batch has loaded, then swaps to its review. */
async function openReview(page: Page, mode: "upload" | "resume"): Promise<Locator> {
  await page.goto("/transactions");
  // By name: the category picker's popover is a dialog too.
  const dialog = page.getByRole("dialog", { name: /Import bank transactions|Review your import/ });
  if (mode === "upload") {
    await page.getByRole("button", { name: "Import bank transactions" }).click();
    await dialog.getByRole("radio", { name: /Custom CSV/ }).click();
    await dialog.locator('input[type="file"]').setInputFiles({
      name: "statement.csv",
      mimeType: "text/csv",
      buffer: statementCsv(),
    });
    await dialog.getByRole("button", { name: "Upload and review" }).click();
  } else {
    // The banner only appears once the pending batch has loaded.
    await page.getByRole("region", { name: "Pending import" }).getByRole("button", { name: "Resume review" }).click();
  }
  await expect(dialog.getByRole("heading", { name: "Review your import" })).toBeVisible();
  return dialog;
}

test("typing a note in a long review keeps up", async ({ page }) => {
  const dialog = await openReview(page, "upload");
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
  const dialog = await openReview(page, "resume");
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
});

test("the categorization review is the import's review", async ({ page }) => {
  // A second account, so rows can be marked as transfers.
  const created = await page.request.post("/api/accounts", { data: { name: "Banco B", type: "bank" } });
  expect(created.ok()).toBeTruthy();

  await page.goto("/budgets");
  const block = page.getByRole("region", { name: "Uncategorized spending" });
  await block.getByRole("button", { name: "Categorize now" }).click();

  // No live LLM in e2e: every uncategorized row is still listed, no suggestions.
  const review = page.getByRole("dialog", { name: "Review uncategorized" });
  const notes = review.getByRole("textbox", { name: "Note" });
  await expect(notes).toHaveCount(ROWS - 2);
  const pickers = review.getByRole("button", { name: "Category" });
  await expect(review.getByRole("button", { name: "Apply changes" })).toBeDisabled();

  // Row 1: category and note.
  await pickers.nth(0).click();
  await page.getByPlaceholder("Search or create…").fill("Mascotas");
  await page.getByRole("option", { name: "Mascotas", exact: true }).click();
  await notes.nth(0).fill("Comida del perro");

  // Row 2: a transfer to the new account, same control as the import.
  await pickers.nth(1).click();
  await page.getByPlaceholder("Search or create…").fill("Banco B");
  await page.getByRole("option", { name: "Transfer → Banco B" }).click();
  await expect(pickers.nth(1)).toHaveText(/Transfer → Banco B/);

  await review.getByRole("button", { name: "Apply changes" }).click();
  await expect(review).toBeHidden();
  // Both rows are resolved; the rest are untouched.
  await expect(block).toContainText(`${ROWS - 4} movements`);

  await page.goto("/transactions");
  await expect(page.getByText("Comida del perro")).toBeVisible();
  await expect(page.getByText(/Transfer → Banco B/).first()).toBeVisible();
});
