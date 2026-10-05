import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { Api, pinClock, resetDb } from "./support/app";

/* unified-transaction-review, task 5.4 — the review of uncategorized
   transactions, scripted:
   1. AI suggestions arrive as defaults with confidence badges (low first);
      a changed row loses its badge; apply writes what was kept;
   2. a confirmed row is marked "Transfer → <account>" from the review;
   3. a row mirroring an existing transfer is linked ("Link them") and the
      duplicate disappears.
   No live LLM in e2e: test 1 injects suggestions into the review response
   in the browser (the backend's AI call is covered by pytest with a mocked
   service). Steps share one database and run in order. */

test.describe.configure({ mode: "serial" });

const MONTH = "2026-10";

interface Txn {
  id: string;
  account_id: string;
  description: string | null;
  amount_cents: number;
  category_id: string | null;
  payee_name: string | null;
  transfer_pair_id: string | null;
}

let api: Api;
let request: APIRequestContext;
let categories: Record<string, string>;
let bbva: string;
let bancoB: string;

async function json<T>(response: Awaited<ReturnType<APIRequestContext["get"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()}`).toBeTruthy();
  return response.json() as Promise<T>;
}

async function transactions(): Promise<Txn[]> {
  return json<Txn[]>(await request.get(`/api/transactions?month=${MONTH}`));
}

async function byDescription(description: string): Promise<Txn> {
  const found = (await transactions()).find((t) => t.description === description);
  expect(found, `transaction "${description}"`).toBeTruthy();
  return found as Txn;
}

/** Bank statement into BBVA, confirmed with nothing picked: every row
    stays uncategorized (no AI in e2e). */
async function importUncategorized(): Promise<void> {
  const csv = [
    "date,amount,description,category,balance",
    "10/10/2026,-45.20,MERCADONA COMPRA,,",
    "09/10/2026,-60.00,VETERINARIO,,",
    "08/10/2026,-12.00,FARMACIA,,",
    "07/10/2026,-200.00,TRASPASO A BANCO B,,",
  ].join("\n");
  const batch = await json<{ id: string; row_count: number }>(
    await request.post("/api/imports", {
      multipart: {
        bank: "custom",
        account_id: bbva,
        file: { name: "bbva.csv", mimeType: "text/csv", buffer: Buffer.from(csv, "utf8") },
      },
    }),
  );
  expect(batch.row_count).toBe(4);
  await json(await request.post(`/api/imports/${batch.id}/confirm`, { data: {} }));
}

async function openReview(page: Page) {
  await page.goto("/transactions");
  await page.getByRole("button", { name: "Review uncategorized" }).click();
  const review = page.getByRole("dialog", { name: "Review uncategorized" });
  await expect(review.getByRole("group").first()).toBeVisible();
  return review;
}

test.beforeAll(async ({ playwright, baseURL }) => {
  resetDb();
  request = await playwright.request.newContext({ baseURL });
  api = new Api(request);
  categories = await api.categories();
  bbva = (await json<{ id: string }>(await request.post("/api/accounts", { data: { name: "BBVA", type: "bank" } }))).id;
  bancoB = (
    await json<{ id: string }>(await request.post("/api/accounts", { data: { name: "Banco B", type: "bank" } }))
  ).id;
  await importUncategorized();
});

test.beforeEach(async ({ page }) => {
  await pinClock(page);
});

test("AI suggestions are defaults with confidence badges", async ({ page }) => {
  // Inject what the model would propose into the real review response.
  await page.route("**/api/transactions/review", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    for (const row of body.transactions) {
      if (row.description === "MERCADONA COMPRA") {
        Object.assign(row, {
          suggested_category_id: categories["Supermercado"],
          suggested_payee: "Mercadona",
          confidence: "high",
        });
      }
      if (row.description === "FARMACIA") {
        Object.assign(row, {
          suggested_category_id: categories["Ocio"],
          suggested_payee: null,
          confidence: "low",
        });
      }
    }
    await route.fulfill({ response, json: body });
  });

  const review = await openReview(page);
  // Only spending needs a category: four BBVA outflows, no income yet.
  await expect(review).toContainText("4 transactions need a category");
  await expect(review).not.toContainText("ready to assign —");
  const rows = review.getByRole("group");
  // Low confidence first, then high, then rows without a suggestion.
  await expect(rows.nth(0)).toHaveAccessibleName("FARMACIA");
  await expect(rows.nth(1)).toHaveAccessibleName("MERCADONA COMPRA");

  const mercadona = review.getByRole("group", { name: "MERCADONA COMPRA" });
  await expect(mercadona.getByRole("button", { name: "Category" })).toHaveText(/Supermercado/);
  await expect(mercadona.getByText("high", { exact: true })).toBeVisible();
  await expect(mercadona.getByPlaceholder("e.g. Mercadona")).toHaveValue("Mercadona");

  // Rejecting a suggestion: the row goes back to "Uncategorized", no badge.
  const farmacia = review.getByRole("group", { name: "FARMACIA" });
  await expect(farmacia.getByText("low", { exact: true })).toBeVisible();
  await farmacia.getByRole("button", { name: "Category" }).click();
  await page.getByRole("option", { name: "Uncategorized", exact: true }).click();
  await expect(farmacia.getByText("low", { exact: true })).toHaveCount(0);

  await review.getByRole("button", { name: "Apply changes" }).click();
  await expect(review).toBeHidden();

  // The kept suggestion is written; the rejected and untouched rows aren't.
  const written = await byDescription("MERCADONA COMPRA");
  expect(written.category_id).toBe(categories["Supermercado"]);
  expect(written.payee_name).toBe("Mercadona");
  expect((await byDescription("FARMACIA")).category_id).toBeNull();
  expect((await byDescription("VETERINARIO")).category_id).toBeNull();
});

test("a confirmed row becomes a transfer from the review", async ({ page }) => {
  const before = await json<{ income_cents: number; uncategorized_cents: number }>(
    await request.get(`/api/budget/${MONTH}`),
  );

  const review = await openReview(page);
  const traspaso = review.getByRole("group", { name: "TRASPASO A BANCO B" });
  await traspaso.getByRole("button", { name: "Category" }).click();
  await page.getByPlaceholder("Search or create…").fill("Banco B");
  await page.getByRole("option", { name: "Transfer → Banco B" }).click();
  await review.getByRole("button", { name: "Apply changes" }).click();
  await expect(review).toBeHidden();

  // Linked twins: −200 in BBVA, +200 in Banco B, no category on either.
  // The twin copies the note, so pick the near side by its sign.
  const near = (await transactions()).find(
    (t) => t.description === "TRASPASO A BANCO B" && t.amount_cents < 0,
  ) as Txn;
  expect(near.account_id).toBe(bbva);
  expect(near.transfer_pair_id).not.toBeNull();
  const twin = (await transactions()).find(
    (t) => t.transfer_pair_id === near.transfer_pair_id && t.id !== near.id,
  );
  expect(twin?.account_id).toBe(bancoB);
  expect(twin?.amount_cents).toBe(20000);
  expect(twin?.category_id).toBeNull();

  // The budget plane never sees a transfer; it no longer waits for a category.
  const after = await json<{ income_cents: number; uncategorized_cents: number }>(
    await request.get(`/api/budget/${MONTH}`),
  );
  expect(after.income_cents).toBe(before.income_cents);
  expect(after.uncategorized_cents).toBe(before.uncategorized_cents - 20000);

  await expect(page.getByText("Transfer → Banco B").first()).toBeVisible();
});

test("a row mirroring an existing transfer is linked, not duplicated", async ({ page }) => {
  // A transfer recorded by hand, and Banco B's side entered again as income.
  await json(
    await request.post("/api/transfers", {
      data: { from_account_id: bbva, to_account_id: bancoB, amount_cents: 15000, date: "2026-10-10" },
    }),
  );
  await json(
    await request.post("/api/transactions", {
      data: {
        amount_cents: 15000,
        kind: "income",
        account_id: bancoB,
        note: "Ingreso duplicado",
        date: "2026-10-12",
      },
    }),
  );

  const review = await openReview(page);
  // The income isn't counted as needing a category: it's ready to assign.
  await expect(review).toContainText("2 transactions need a category");
  await expect(review).toContainText("1 income is ready to assign");
  const duplicate = review.getByRole("group", { name: "Ingreso duplicado" });
  await expect(duplicate).toContainText("Looks like the transfer from BBVA");
  await duplicate.getByRole("button", { name: "Link them" }).click();
  await expect(duplicate).toContainText("won't be added twice");
  await review.getByRole("button", { name: "Apply changes" }).click();
  await expect(review).toBeHidden();

  // Exactly one +150,00 € in Banco B: the transfer's own twin.
  const inB = (await transactions()).filter((t) => t.account_id === bancoB && t.amount_cents === 15000);
  expect(inB).toHaveLength(1);
  expect(inB[0].transfer_pair_id).not.toBeNull();
  expect(inB[0].description).not.toBe("Ingreso duplicado");
});
