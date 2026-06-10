/* Typed client for the BFF (`/api/*` Route Handlers → FastAPI).
   Types mirror backend/app/schemas.py — keep the two in sync by hand
   (design D2). Presentation (tone) is derived here, never served. */

import type { ChipTone } from "@/components/ui/IconChip";

// ---- Types mirroring backend/app/schemas.py --------------------------------

export type SuggestionState = "draft" | "confirmed" | "edited";

export interface BudgetCategoryView {
  id: string;
  name: string;
  icon: string;
  assigned_cents: number;
  spent_cents: number;
  rollover_cents: number;
  available_cents: number;
  suggestion_cents: number | null;
  suggestion_state: SuggestionState;
  last_month_assigned_cents: number | null;
  avg_3m_cents: number | null;
  last_month_spent_cents: number | null;
}

export interface BudgetGroupView {
  id: string;
  name: string;
  sort_order: number;
  categories: BudgetCategoryView[];
}

export interface BudgetMonthView {
  month: string; // "2026-06"
  income_cents: number;
  to_be_assigned_cents: number;
  groups: BudgetGroupView[];
}

export interface AssignResponse {
  category_id: string;
  assigned_cents: number;
  suggestion_state: string;
  to_be_assigned_cents: number;
}

export interface CategoryOut {
  id: string;
  name: string;
  icon: string;
  archived: boolean;
}

export interface CategoryGroupOut {
  id: string;
  name: string;
  sort_order: number;
  categories: CategoryOut[];
}

export interface TransactionCreate {
  amount_cents: number;
  category_id: string;
  kind?: "expense" | "income";
  note?: string;
  date?: string; // "YYYY-MM-DD"
}

export interface TransactionOut {
  id: string;
  account_id: string;
  category_id: string | null;
  date: string;
  amount_cents: number; // signed: expenses negative, income positive
  currency: string;
  description: string | null;
  source: string;
  status: string;
}

// ---- Fetch helpers ----------------------------------------------------------

/** Machine-readable API error ({"code": "<snake_case>"} per §6.7). */
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
  ) {
    super(code);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.code ?? "unknown_error", res.status);
  }
  return res.json() as Promise<T>;
}

export const fetchBudgetMonth = (month: string) =>
  request<BudgetMonthView>(`/budget/${month}`);

export const putAssignment = (
  month: string,
  categoryId: string,
  amountCents: number,
) =>
  request<AssignResponse>(`/budget/${month}/assignments/${categoryId}`, {
    method: "PUT",
    body: JSON.stringify({ amount_cents: amountCents }),
  });

export const confirmSuggestions = (month: string, categoryIds: string[]) =>
  request<BudgetMonthView>(`/budget/${month}/confirm-suggestions`, {
    method: "POST",
    body: JSON.stringify({ category_ids: categoryIds }),
  });

export const fetchCategories = () =>
  request<CategoryGroupOut[]>("/categories");

export const fetchTransactions = (month?: string) =>
  request<TransactionOut[]>(
    month ? `/transactions?month=${month}` : "/transactions",
  );

export const createTransaction = (input: TransactionCreate) =>
  request<TransactionOut>("/transactions", {
    method: "POST",
    body: JSON.stringify(input),
  });

// ---- Presentation -----------------------------------------------------------

/** Current calendar month as "YYYY-MM" (design D4). */
export function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/* Chip tone is presentation, derived from the category icon — the API never
   serves it. Mirrors the tones the mock data used per category. */
const ICON_TONES: Record<string, ChipTone> = {
  home: "violet",
  zap: "info",
  "shopping-bag": "mint",
  coffee: "warning",
  flame: "expense",
  "credit-card": "info",
  receipt: "violet",
  users: "mint",
  "piggy-bank": "mint",
};

export function toneForCategory(icon: string): ChipTone {
  return ICON_TONES[icon] ?? "violet";
}
