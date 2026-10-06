import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { euroCents } from "../../src/lib/format";
import { E2E_TODAY } from "./constants";

export { euroCents };

/** Clean, seeded e2e database: migrate, truncate, dev user + default tree. */
export function resetDb(): void {
  execFileSync("uv", ["run", "python", "-m", "app.e2e_reset"], {
    cwd: path.resolve(__dirname, "../../../backend"),
    stdio: "inherit",
  });
}

/** The browser lives on the same day as the API (FIXED_TODAY). */
export async function pinClock(page: Page): Promise<void> {
  await page.clock.setFixedTime(new Date(`${E2E_TODAY}T12:00:00+02:00`));
}

/** Setup through the BFF, like the browser would — for data the scenario
    needs but isn't what the test is about. */
export class Api {
  constructor(private readonly request: APIRequestContext) {}

  private async send(method: "GET" | "POST" | "PUT", url: string, data?: unknown) {
    const response = await this.request.fetch(`/api${url}`, { method, data });
    expect(response.ok(), `${method} ${url} → ${response.status()} ${await response.text()}`).toBeTruthy();
    return response.status() === 204 ? null : response.json();
  }

  /** Category name → id, across every group. */
  async categories(): Promise<Record<string, string>> {
    const groups: { id: string; categories: { id: string; name: string }[] }[] = await this.send("GET", "/categories");
    return Object.fromEntries(groups.flatMap((g) => g.categories.map((c) => [c.name, c.id])));
  }

  async firstGroupId(): Promise<string> {
    const groups: { id: string }[] = await this.send("GET", "/categories");
    return groups[0].id;
  }

  async createCategory(name: string, groupId: string): Promise<string> {
    return (await this.send("POST", "/categories", { name, group_id: groupId })).id;
  }

  async openMonth(month: string): Promise<void> {
    await this.send("GET", `/budget/${month}`);
  }

  async assign(month: string, categoryId: string, amountCents: number): Promise<void> {
    await this.send("PUT", `/budget/${month}/assignments/${categoryId}`, { amount_cents: amountCents });
  }

  async move(month: string, from: string, to: string, amountCents: number): Promise<void> {
    await this.send("POST", `/budget/${month}/moves`, {
      from_category_id: from,
      to_category_id: to,
      amount_cents: amountCents,
    });
  }

  async income(amountCents: number, date: string, payee?: string): Promise<void> {
    await this.send("POST", "/transactions", { amount_cents: amountCents, kind: "income", date, payee });
  }

  /** Expected income (income-schedules); never touches the budget. */
  async incomeSchedule(body: Record<string, unknown>): Promise<void> {
    await this.send("POST", "/income-schedules", body);
  }

  async expense(categoryId: string, amountCents: number, date: string): Promise<void> {
    await this.send("POST", "/transactions", { amount_cents: amountCents, category_id: categoryId, date });
  }
}
