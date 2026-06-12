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

export interface CategoryCreate {
  name: string;
  icon?: string;
  group_id: string;
}

export interface CategoryUpdate {
  name?: string;
  icon?: string;
  group_id?: string; // move between groups
  archived?: boolean;
}

export interface GroupCreate {
  name: string;
}

export interface GroupUpdate {
  name?: string;
  sort_order?: number;
}

export interface PayeeOut {
  id: string;
  name: string;
  // Category of the most recent confirmed transaction with this payee —
  // drives the autocomplete category prefill. Null when none.
  last_category_id: string | null;
}

export interface TransactionCreate {
  amount_cents: number;
  category_id: string;
  kind?: "expense" | "income";
  payee?: string; // find-or-create by trimmed name, case-insensitive
  note?: string;
  date?: string; // "YYYY-MM-DD"
}

export interface TransactionUpdate {
  amount_cents?: number; // positive magnitude, signed server-side
  kind?: "expense" | "income"; // omitted keeps the row's current sign
  category_id?: string;
  payee?: string; // "" clears the payee
  note?: string | null; // null clears the description
  date?: string; // "YYYY-MM-DD"
}

export interface TransactionOut {
  id: string;
  account_id: string;
  category_id: string | null;
  payee_id: string | null;
  payee_name: string | null; // joined server-side; AI-resolved at import staging
  date: string;
  amount_cents: number; // signed: expenses negative, income positive
  currency: string;
  description: string | null;
  source: string;
  status: string;
}

export type SuggestionConfidence = "high" | "medium" | "low";

export interface CategoryProposal {
  transaction_id: string;
  category_id: string | null;
  payee: string | null; // cleaned merchant/payer name, null when unclear
  confidence: SuggestionConfidence;
}

export interface CategoryAssignment {
  category_id?: string; // omitted = leave category untouched
  payee?: string; // omitted = leave payee untouched; "" clears
}

export type ImportBank = "bbva" | "sabadell" | "custom";

export interface ImportBatchView {
  id: string;
  account_id: string;
  source: string;
  filename: string;
  status: "staged" | "confirmed" | "discarded";
  row_count: number;
  skipped_duplicates: number;
  transactions: TransactionOut[];
}

export interface SummaryWeek {
  start: string; // ISO date, bucket's first day clamped to the month
  spent_cents: number;
  income_cents: number;
}

export interface SummaryView {
  month: string;
  balance_cents: number; // all-time sum of confirmed transactions
  income_cents: number;
  expense_cents: number;
  weeks: SummaryWeek[];
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
    // FastAPI nests codes under "detail"; the BFF's own errors are flat.
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
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

export const fetchPayees = () => request<PayeeOut[]>("/payees");

export const createCategory = (input: CategoryCreate) =>
  request<CategoryOut>("/categories", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateCategory = (id: string, patch: CategoryUpdate) =>
  request<CategoryOut>(`/categories/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const createCategoryGroup = (input: GroupCreate) =>
  request<CategoryGroupOut>("/categories/groups", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateCategoryGroup = (id: string, patch: GroupUpdate) =>
  request<CategoryGroupOut>(`/categories/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const deleteCategoryGroup = async (id: string): Promise<void> => {
  const res = await fetch(`/api/categories/groups/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
  }
};

export const fetchSummary = (month: string) =>
  request<SummaryView>(`/summary/${month}`);

export const fetchTransactions = (month?: string) =>
  request<TransactionOut[]>(
    month ? `/transactions?month=${month}` : "/transactions",
  );

export const createTransaction = (input: TransactionCreate) =>
  request<TransactionOut>("/transactions", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateTransaction = (id: string, patch: TransactionUpdate) =>
  request<TransactionOut>(`/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const suggestCategories = (transactionIds?: string[]) =>
  request<{ proposals: CategoryProposal[] }>("/transactions/suggest-categories", {
    method: "POST",
    body: JSON.stringify(
      transactionIds ? { transaction_ids: transactionIds } : {},
    ),
  });

export const applyCategories = (
  assignments: Record<string, CategoryAssignment>,
) =>
  request<{ applied: number }>("/transactions/apply-categories", {
    method: "POST",
    body: JSON.stringify({ assignments }),
  });

export const deleteTransaction = async (id: string): Promise<void> => {
  const res = await fetch(`/api/transactions/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
  }
};

export async function uploadImport(
  file: File,
  bank: ImportBank,
): Promise<ImportBatchView> {
  const form = new FormData();
  form.append("file", file);
  form.append("bank", bank);
  // No Content-Type header — fetch sets the multipart boundary.
  const res = await fetch("/api/imports", { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
  }
  return res.json() as Promise<ImportBatchView>;
}

export const fetchImport = (id: string) =>
  request<ImportBatchView>(`/imports/${id}`);

/** The user's staged batch, or null when none (404 no_pending_import). */
export async function fetchPendingImport(): Promise<ImportBatchView | null> {
  try {
    return await request<ImportBatchView>("/imports/pending");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export const confirmImport = (
  id: string,
  overrides: Record<string, string | null>,
  // txn_id -> payee name ("" clears; backend resolves find-or-create)
  payeeOverrides: Record<string, string> = {},
) =>
  request<ImportBatchView>(`/imports/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify({ overrides, payee_overrides: payeeOverrides }),
  });

export const discardImport = async (id: string): Promise<void> => {
  const res = await fetch(`/api/imports/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
  }
};

// ---- Onboarding -------------------------------------------------------------

export type OnboardingInputKind = "chips" | "checkboxes" | "text" | "money";

/** One transcript entry; assistant turns carry the quick-input hints. */
export interface OnboardingTranscriptEntry {
  role: "user" | "assistant";
  content: string;
  input_kind?: OnboardingInputKind;
  options?: string[];
  done?: boolean;
}

export interface OnboardingProposedCategory {
  name: string;
  icon: string;
}

export interface OnboardingProposedGroup {
  name: string;
  categories: OnboardingProposedCategory[];
}

export interface OnboardingIncome {
  sources: string[];
  expected_monthly_cents: number | null;
  income_day: number | null;
}

export interface OnboardingProposal {
  category_groups: OnboardingProposedGroup[];
  payers: string[];
  payees: string[];
  income: OnboardingIncome;
}

export interface OnboardingSessionView {
  id: string;
  status: "active" | "completed" | "abandoned";
  prompt_version: string;
  transcript: OnboardingTranscriptEntry[];
  proposal: OnboardingProposal | null;
}

/** The reviewed proposal: checked items only, renames applied, additions included. */
export interface OnboardingFinalizePayload {
  category_groups: OnboardingProposedGroup[];
  payers: string[];
  payees: string[];
  income?: OnboardingIncome;
}

export interface OnboardingFinalizeResult {
  categories_created: number;
  payees_created: number;
}

export interface OnboardingStatus {
  has_completed: boolean;
  has_active: boolean;
}

export const fetchOnboardingStatus = () =>
  request<OnboardingStatus>("/onboarding/status");

export const startOnboarding = () =>
  request<OnboardingSessionView>("/onboarding/start", { method: "POST" });

export const fetchOnboardingSession = () =>
  request<OnboardingSessionView>("/onboarding/session");

export const sendOnboardingMessage = (message: string) =>
  request<OnboardingSessionView>("/onboarding/messages", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const finalizeOnboarding = (
  sessionId: string,
  payload: OnboardingFinalizePayload,
) =>
  request<OnboardingFinalizeResult>(`/onboarding/${sessionId}/finalize`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const useOnboardingTemplate = () =>
  request<OnboardingFinalizeResult>("/onboarding/template", { method: "POST" });

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
