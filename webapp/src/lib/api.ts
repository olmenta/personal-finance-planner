/* Typed client for the BFF (`/api/*` Route Handlers → FastAPI).
   Types mirror backend/app/schemas.py — keep the two in sync by hand
   (design D2). Presentation (tone) is derived here, never served. */

import type { ChipTone } from "@/components/ui/IconChip";

// ---- Types mirroring backend/app/schemas.py --------------------------------

export type SuggestionState = "draft" | "confirmed" | "edited";

export interface CoverSuggestion {
  /** null = cover from To Be Assigned */
  source_category_id: string | null;
  amount_cents: number;
}

export type CategoryKind = "flexible" | "scheduled" | "savings";

export interface BudgetCategoryView {
  id: string;
  name: string;
  icon: string;
  /** credit_payment: a card's payment category (spent = payments to the card). */
  kind: CategoryKind | "credit_payment";
  payment_account_id: string | null;
  /** Computed from payment schedules; null when the category has none. */
  normal_cents: number | null;
  catch_up_cents: number | null;
  assigned_cents: number;
  spent_cents: number;
  rollover_cents: number;
  available_cents: number;
  overspent_cents: number;
  /** Last month's overspending of this category, reset instead of carried. */
  rollover_reset_cents: number;
  /** Card spending not covered by the available — stays as card debt. */
  credit_overspent_cents: number;
  cover_suggestion: CoverSuggestion | null;
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
  /** Cumulative: carries over between months — never recompute client-side. */
  to_be_assigned_cents: number;
  /** Previous month's To Be Assigned. */
  carried_in_cents: number;
  /** Previous month's uncovered cash overspending, deducted from this month. */
  overspent_deducted_cents: number;
  groups: BudgetGroupView[];
}

export interface MoveRequest {
  /** null = draw from To Be Assigned */
  from_category_id: string | null;
  to_category_id: string;
  amount_cents: number;
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
  /** Derived: scheduled (has payments) | savings (flag) | flexible. */
  kind: CategoryKind;
  savings: boolean;
  /** Set on a credit card's system payment category. */
  payment_account_id: string | null;
}

// ---- Payment schedules, month overview, plan (category-targets) -----------

export type SchedulePattern =
  | "monthly"
  | "some_months"
  | "annual"
  | "every_n"
  | "once"
  | "no_date";

export interface ScheduleIn {
  name: string;
  amount_cents: number;
  pattern: SchedulePattern;
  months?: number[];
  month?: number;
  every_n?: number;
  start_month?: string; // "YYYY-MM"
  count?: number;
  once_month?: string; // "YYYY-MM"
  day?: number | null;
  estimated?: boolean;
}

export interface ScheduleOut {
  id: string;
  category_id: string;
  name: string;
  amount_cents: number;
  pattern: SchedulePattern;
  months: number[] | null;
  month: number | null;
  every_n: number | null;
  start_month: string | null;
  count: number | null;
  once_month: string | null;
  day: number | null;
  estimated: boolean;
}

export interface OverviewPaidItem {
  category_id: string;
  category_name: string;
  /** Schedule name; null = the category's other spending. */
  name: string | null;
  day: number | null;
  amount_cents: number;
}

export interface OverviewAmountItem {
  category_id: string;
  name: string;
  group: string;
  amount_cents: number;
  spent_cents: number | null;
}

export interface OverviewPending {
  category_id: string;
  category_name: string;
  schedule_id: string;
  name: string;
  day: number | null;
  amount_cents: number;
  covered_cents: number;
  short_cents: number;
  estimated: boolean;
}

export interface OverviewView {
  month: string;
  today: string;
  paid: { total_cents: number; items: OverviewPaidItem[] };
  to_pay: OverviewPending[];
  to_pay_total_cents: number;
  covered_cents: number;
  left_to_spend: { total_cents: number; items: OverviewAmountItem[] };
  saved: { total_cents: number; items: OverviewAmountItem[] };
  overspent_cents: number;
  to_be_assigned_cents: number;
  /** = covered + left_to_spend + saved + to_be_assigned − overspent */
  accounts_cents: number;
}

export interface UpcomingOccurrence {
  category_id: string;
  category_name: string;
  schedule_id: string;
  name: string;
  day: number | null;
  amount_cents: number;
  estimated: boolean;
  covered: boolean | null;
  short_cents: number | null;
}

export interface UpcomingMonth {
  month: string;
  occurrences: UpcomingOccurrence[];
  payments_cents: number;
  short_cents: number | null;
  flexible_budget_cents: number | null;
  flexible_funded_cents: number | null;
  set_aside_wanted_cents: number | null;
  set_aside_funded_cents: number | null;
  unassigned_cents: number | null;
}

export interface UpcomingView {
  income_known: boolean;
  income_cents: number | null;
  months: UpcomingMonth[];
}

export interface PlanSummary {
  month: string;
  income_known: boolean;
  income_cents: number | null;
  scheduled_cents: number;
  flexible_cents: number;
  goals_cents: number;
  costs_cents: number;
  gap_cents: number | null;
  gap_monthly_cents: number | null;
}

export interface CategoryGroupOut {
  id: string;
  name: string;
  sort_order: number;
  /** "Tarjetas de crédito": not editable via category CRUD. */
  system: boolean;
  categories: CategoryOut[];
}

export interface CategoryCreate {
  name: string;
  icon?: string;
  group_id: string;
  savings?: boolean;
}

export interface CategoryUpdate {
  name?: string;
  icon?: string;
  group_id?: string; // move between groups
  archived?: boolean;
  savings?: boolean;
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
  category_id?: string; // required for expenses; income may go uncategorized
  kind?: "expense" | "income";
  payee?: string; // find-or-create by trimmed name, case-insensitive
  note?: string;
  date?: string; // "YYYY-MM-DD"
  account_id?: string; // omitted = the main account
}

export interface TransactionUpdate {
  amount_cents?: number; // positive magnitude, signed server-side
  category_id?: string | null; // absent = untouched, null = clear (un-refund)
  kind?: "expense" | "income"; // omitted keeps the row's current sign
  payee?: string; // "" clears the payee
  note?: string | null; // null clears the description
  date?: string; // "YYYY-MM-DD"
  account_id?: string; // moves the row between registers
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
  /** Transfer twins share a pair id; null for ordinary rows. */
  transfer_pair_id: string | null;
  /** The other side's account (transfers only). */
  transfer_account_id: string | null;
}

// ---- Accounts & transfers ---------------------------------------------------

export type AccountType = "cash" | "bank" | "credit";

export interface AccountOut {
  id: string;
  name: string;
  type: AccountType;
  institution: string | null;
  archived: boolean;
  /** Derived: sum of confirmed transactions. Credit balances are negative. */
  balance_cents: number;
  /** Oldest active account — the default for new entries. */
  is_main: boolean;
  // Credit accounts only (null otherwise).
  payment_day: number | null;
  suggested_payment_day: number | null;
  payment_category_id: string | null;
  payment_available_cents: number | null;
  uncovered_debt_cents: number | null;
}

export interface AccountCreate {
  name: string;
  type: AccountType;
  institution?: string;
  /** Signed: positive cash on hand, negative pre-existing card debt. */
  opening_balance_cents?: number;
  payment_day?: number; // credit only
}

export interface AccountUpdate {
  name?: string;
  institution?: string | null;
  archived?: boolean;
  payment_day?: number | null; // null clears
}

export interface TransferCreate {
  from_account_id: string;
  to_account_id: string;
  amount_cents: number;
  date?: string;
  note?: string;
}

export interface TransferUpdate {
  amount_cents?: number;
  date?: string;
  note?: string | null; // null clears
}

export interface TransferOut {
  pair_id: string;
  from_account_id: string;
  to_account_id: string;
  amount_cents: number;
  date: string;
  note: string | null;
  out_transaction_id: string;
  in_transaction_id: string;
}

/** An existing transfer twin a staged row seems to mirror — never applied silently. */
export interface TwinMatch {
  transaction_id: string;
  pair_id: string;
  other_account_id: string;
  date: string;
}

export interface StagedTransactionOut extends TransactionOut {
  match: TwinMatch | null;
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
  transactions: StagedTransactionOut[];
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

export const moveMoney = (month: string, body: MoveRequest) =>
  request<BudgetMonthView>(`/budget/${month}/moves`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const confirmSuggestions = (month: string, categoryIds: string[]) =>
  request<BudgetMonthView>(`/budget/${month}/confirm-suggestions`, {
    method: "POST",
    body: JSON.stringify({ category_ids: categoryIds }),
  });

export const fetchSchedules = (categoryId: string) =>
  request<ScheduleOut[]>(`/categories/${categoryId}/schedules`);

export const createSchedule = (categoryId: string, body: ScheduleIn) =>
  request<ScheduleOut>(`/categories/${categoryId}/schedules`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateSchedule = (id: string, body: Partial<ScheduleIn>) =>
  request<ScheduleOut>(`/schedules/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export async function deleteSchedule(id: string): Promise<void> {
  const res = await fetch(`/api/schedules/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("delete_failed", res.status);
}

export const fetchOverview = (month: string) => request<OverviewView>(`/overview/${month}`);

export const fetchUpcoming = (from: string) =>
  request<UpcomingView>(`/plan/upcoming?from=${from}`);

export const fetchPlanSummary = (from: string) =>
  request<PlanSummary>(`/plan/summary?from=${from}`);

export const fetchExpectedIncome = () =>
  request<{ expected_monthly_cents: number | null }>("/plan/income");

export const putExpectedIncome = (cents: number) =>
  request<{ expected_monthly_cents: number | null }>("/plan/income", {
    method: "PUT",
    body: JSON.stringify({ expected_monthly_cents: cents }),
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

async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      body?.detail?.code ?? body?.code ?? "unknown_error",
      res.status,
    );
  }
}

export const fetchAccounts = () => request<AccountOut[]>("/accounts");

export const createAccount = (input: AccountCreate) =>
  request<AccountOut>("/accounts", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateAccount = (id: string, patch: AccountUpdate) =>
  request<AccountOut>(`/accounts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const fetchTransfer = (pairId: string) =>
  request<TransferOut>(`/transfers/${pairId}`);

export const createTransfer = (input: TransferCreate) =>
  request<TransferOut>("/transfers", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateTransfer = (pairId: string, patch: TransferUpdate) =>
  request<TransferOut>(`/transfers/${pairId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const deleteTransfer = (pairId: string) =>
  requestVoid(`/transfers/${pairId}`, { method: "DELETE" });

export const unlinkTransfer = (pairId: string) =>
  requestVoid(`/transfers/${pairId}/unlink`, { method: "POST" });

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
  accountId?: string, // omitted = the main account
): Promise<ImportBatchView> {
  const form = new FormData();
  form.append("file", file);
  form.append("bank", bank);
  if (accountId) form.append("account_id", accountId);
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
  // txn_id -> other account: the row is a transfer, twin created on confirm
  transferOverrides: Record<string, string> = {},
  // staged rows whose match suggestion was accepted (existing twin adopted)
  acceptMatches: string[] = [],
) =>
  request<ImportBatchView>(`/imports/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify({
      overrides,
      payee_overrides: payeeOverrides,
      transfer_overrides: transferOverrides,
      accept_matches: acceptMatches,
    }),
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

export interface OnboardingProposedAccount {
  name: string;
  type: "bank" | "credit";
}

export interface OnboardingProposal {
  accounts?: OnboardingProposedAccount[];
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
  accounts: OnboardingProposedAccount[];
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
