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
  /** The month's outflows still without a category (reported only). */
  uncategorized_cents: number;
  uncategorized_count: number;
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
  /** Set when the schedule is managed from "What you owe". */
  debt_id?: string | null;
}

// ---- Income schedules (income-schedules) -------------------------------------

/** Income uses the payment patterns minus "no_date": undated income can't be planned. */
export type IncomePattern = Exclude<SchedulePattern, "no_date">;

export interface IncomeScheduleIn extends Omit<ScheduleIn, "pattern"> {
  pattern: IncomePattern;
  /** Payer name, resolved to a payee by the backend; "" clears it. */
  payer?: string | null;
}

export interface IncomeScheduleOut extends Omit<ScheduleOut, "category_id" | "pattern"> {
  pattern: IncomePattern;
  payee_id: string | null;
  payer: string | null;
  /** Σ of its occurrences over the next 12 months. */
  yearly_cents: number;
}

export type IncomeStatus = "received" | "pending" | "late" | "missed";

export interface IncomeOccurrence {
  schedule_id: string;
  name: string;
  payee_id: string | null;
  payer: string | null;
  day: number | null;
  amount_cents: number;
  estimated: boolean;
  received_cents: number;
  /** received − expected; null unless received. */
  difference_cents: number | null;
  status: IncomeStatus;
  transaction_ids: string[];
}

export interface UnplannedIncome {
  transaction_id: string;
  payee_id: string | null;
  label: string;
  date: string;
  amount_cents: number;
}

export interface MonthIncomeView {
  month: string;
  has_schedules: boolean;
  occurrences: IncomeOccurrence[];
  unplanned: UnplannedIncome[];
  expected_cents: number;
  received_cents: number;
  still_expected_cents: number;
}

export interface OverviewPaidItem {
  category_id: string;
  category_name: string;
  /** Schedule name; null = the category's other spending. */
  name: string | null;
  day: number | null;
  amount_cents: number;
  /** The paid part of a payment that isn't settled yet. */
  partial: boolean;
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
  /** A required debt payment more than 3 days past its day. */
  late: boolean;
}

export interface OverviewView {
  month: string;
  today: string;
  paid: { total_cents: number; items: OverviewPaidItem[] };
  /** Transfers into cards: settlements, kept out of "paid" (purchases already count there). */
  card_payments: { total_cents: number; items: OverviewPaidItem[] };
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
  /** Σ of the month's income-schedule occurrences; null without income schedules. */
  expected_income_cents: number | null;
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
  /** Σ expected income over the 12 months. */
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

/** A confirmed uncategorized row; the AI suggestion is a default, never stored. */
export interface ReviewRowOut extends StagedTransactionOut {
  suggested_category_id: string | null;
  suggested_payee: string | null;
  confidence: SuggestionConfidence | null;
}

export interface ReviewView {
  transactions: ReviewRowOut[];
}

/** The decisions both reviews send: import confirm and review apply. */
export interface ReviewDecisions {
  overrides: Record<string, string | null>; // category id; null clears
  payee_overrides: Record<string, string>; // "" clears; find-or-create
  note_overrides: Record<string, string | null>; // replaces the description; null clears
  transfer_overrides: Record<string, string>; // other account: twin created
  accept_matches: string[]; // existing twin adopted, the row dropped
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

/** fetch to the BFF. A 401 `unauthenticated` means the session ended: send
    the person to sign in and come back to this page (spec: authentication). */
async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 401 && typeof window !== "undefined") {
    const body = await res.clone().json().catch(() => null);
    if (body?.code === "unauthenticated" || body?.detail?.code === "unauthenticated") {
      const here = `${window.location.pathname}${window.location.search}`;
      window.location.assign(`/auth/login?returnTo=${encodeURIComponent(here)}`);
    }
  }
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(`/api${path}`, {
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
  const res = await apiFetch(`/api/schedules/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("delete_failed", res.status);
}

export const fetchOverview = (month: string) => request<OverviewView>(`/overview/${month}`);

export const fetchUpcoming = (from: string) =>
  request<UpcomingView>(`/plan/upcoming?from=${from}`);

export const fetchPlanSummary = (from: string) =>
  request<PlanSummary>(`/plan/summary?from=${from}`);

export const fetchIncomeSchedules = () => request<IncomeScheduleOut[]>("/income-schedules");

export const createIncomeSchedule = (body: IncomeScheduleIn) =>
  request<IncomeScheduleOut>("/income-schedules", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateIncomeSchedule = (id: string, body: Partial<IncomeScheduleIn>) =>
  request<IncomeScheduleOut>(`/income-schedules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export async function deleteIncomeSchedule(id: string): Promise<void> {
  const res = await apiFetch(`/api/income-schedules/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("delete_failed", res.status);
}

// ---- Debts (debts) --------------------------------------------------------------

export type DebtKind = "card" | "loan" | "personal";
export type RatePeriod = "month" | "year";

export interface DebtOut {
  id: string;
  kind: DebtKind;
  category_id: string;
  account_id: string | null;
  name: string;
  lender: string | null;
  owed_cents: number;
  rate_bp: number | null;
  rate_period: RatePeriod | null;
  monthly_rate_bp: number | null;
  minimum_cents: number | null;
  below_minimum: boolean | null;
  required_monthly_cents: number;
  plan_monthly_cents: number | null;
  installment_cents: number | null;
  installments_left: number | null;
  next_month: string | null;
  day: number | null;
  due_month: string | null;
  end_month: string | null;
  paid_off: boolean;
  position: number | null;
  monthly_interest_cents: number | null;
}

export interface DebtsView {
  debts: DebtOut[];
  total_owed_cents: number;
  extra_monthly_cents: number;
  extra_target_debt_id: string | null;
  debt_free_month: string | null;
  cushion: { suggested_cents: number; saved_cents: number };
}

interface DebtRateIn {
  rate_bp?: number | null;
  rate_period?: RatePeriod | null;
}

export type DebtIn =
  | (DebtRateIn & {
      kind: "card";
      account_id: string;
      plan_monthly_cents?: number;
      target_month?: string;
      minimum_cents?: number;
    })
  | (DebtRateIn & {
      kind: "loan";
      name: string;
      installment_cents: number;
      installments_left: number;
      next_month: string;
      day?: number | null;
    })
  | (DebtRateIn & {
      kind: "personal";
      name: string;
      owed_cents: number;
      due_month?: string | null;
      lender?: string | null;
    });

export type DebtUpdate = Partial<{
  rate_bp: number | null;
  rate_period: RatePeriod | null;
  name: string;
  plan_monthly_cents: number;
  target_month: string;
  minimum_cents: number | null;
  installment_cents: number;
  installments_left: number;
  next_month: string;
  day: number | null;
  owed_cents: number;
  due_month: string | null;
  lender: string | null;
}>;

export interface ConvertToLoanIn {
  installment_cents: number;
  installments_left: number;
  next_month: string;
  day?: number | null;
  rate_bp?: number | null;
  rate_period?: RatePeriod | null;
}

export const fetchDebts = () => request<DebtsView>("/debts");

export const createDebt = (body: DebtIn) =>
  request<DebtsView>("/debts", { method: "POST", body: JSON.stringify(body) });

export const updateDebt = (id: string, body: DebtUpdate) =>
  request<DebtsView>(`/debts/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export async function deleteDebt(id: string): Promise<void> {
  const res = await apiFetch(`/api/debts/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("delete_failed", res.status);
}

export const putDebtExtra = (cents: number) =>
  request<DebtsView>("/debts/extra", {
    method: "PUT",
    body: JSON.stringify({ extra_monthly_cents: cents }),
  });

export const convertToLoan = (accountId: string, body: ConvertToLoanIn) =>
  request<DebtsView>(`/accounts/${accountId}/convert-to-loan`, {
    method: "POST",
    body: JSON.stringify(body),
  });

// ---- Coach proposals (coach-proposals) ------------------------------------------

export type ProposalKind =
  | "late_income"
  | "late_debt_payment"
  | "short_months"
  | "overspending"
  | "unassigned"
  | "underspending";

export interface CoachProposal {
  fingerprint: string;
  /** Raise / lower only: send it back to accept exactly what was reviewed. */
  revision: string | null;
  kind: ProposalKind;
  title: string;
  body: string;
  action: "raise" | "lower" | "add_income" | "link_income" | "open";
  amount_cents: number;
  category_id: string | null;
  current_cents: number | null;
  suggested_cents: number | null;
  diff_cents: number | null;
  sources: { category_id: string; name: string; available_cents: number }[] | null;
  schedule_id: string | null;
  payer: string | null;
  href: string | null;
}

export interface CoachProposalsView {
  proposals: CoachProposal[];
  total: number;
}

export const fetchCoachProposals = () => request<CoachProposalsView>("/coach/proposals");

// ---- Home (home) ----------------------------------------------------------------

export interface HomeSummary {
  /** M = T + L + F + U */
  accounts_cents: number;
  covered_cents: number;
  left_to_spend_cents: number;
  saved_cents: number;
  unassigned_cents: number;
  paid_cents: number;
  card_payments_cents: number;
  still_to_pay_cents: number;
  short_cents: number;
}

export type HomeReasonCode =
  | "over_assigned"
  | "overspent_categories"
  | "unbudgeted_card_spending"
  | "uncovered_payments";

export interface HomeReason {
  code: HomeReasonCode;
  amount_cents: number;
  items: { category_id: string; name: string; amount_cents: number }[];
}

export interface HomeView {
  month: string;
  generated_at: string;
  status: "organized" | "needs_organizing" | "no_accounts" | "not_set_up";
  reasons: HomeReason[];
  summary: HomeSummary;
  data: {
    last_transaction_date: string | null;
    uncategorized_count: number;
    pending_import: boolean;
    income_known: boolean;
    limited: boolean;
  };
  future: {
    status: "on_track" | "needs_attention" | "unknown";
    month: string | null;
    short_cents: number;
    set_aside_gap_cents: number;
  };
  priority: CoachProposal | null;
  groups: { key: string; title: string; proposals: CoachProposal[] }[];
  snapshot_version: string;
}

export const fetchHome = () => request<HomeView>("/home");

export async function dismissProposal(fingerprint: string): Promise<void> {
  const res = await apiFetch(`/api/coach/proposals/${encodeURIComponent(fingerprint)}/dismiss`, {
    method: "POST",
  });
  if (!res.ok) throw new ApiError("dismiss_failed", res.status);
}

/** The proposal changed between showing and accepting it (409
    proposal_changed): carries the current version to show instead. */
export class ProposalChangedError extends Error {
  constructor(readonly proposal: CoachProposal) {
    super("proposal_changed");
  }
}

export async function acceptProposal(
  fingerprint: string,
  revision: string,
  fromCategoryId?: string,
): Promise<CoachProposalsView> {
  const res = await apiFetch(`/api/coach/proposals/${encodeURIComponent(fingerprint)}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ revision, ...(fromCategoryId ? { from_category_id: fromCategoryId } : {}) }),
  });
  const body = await res.json().catch(() => null);
  if (res.status === 409 && body?.detail?.code === "proposal_changed") {
    throw new ProposalChangedError(body.detail.proposal as CoachProposal);
  }
  if (!res.ok) throw new ApiError(body?.detail?.code ?? "unknown_error", res.status);
  return body as CoachProposalsView;
}

export const fetchMonthIncome = (month: string) => request<MonthIncomeView>(`/income/${month}`);

/** "This is…": link an unplanned inflow to an expected income in one step
    (spec: income-schedules, one shared income operation). */
export const linkIncome = (transactionId: string, scheduleId: string) =>
  request<MonthIncomeView>("/income/link", {
    method: "POST",
    body: JSON.stringify({ transaction_id: transactionId, schedule_id: scheduleId }),
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
  const res = await apiFetch(`/api/categories/groups/${id}`, { method: "DELETE" });
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
  const res = await apiFetch(`/api${path}`, init);
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

/** Every uncategorized transaction with AI defaults and twin matches. */
export const fetchReview = () =>
  request<ReviewView>("/transactions/review", { method: "POST" });

export const applyReview = (decisions: ReviewDecisions) =>
  request<{ applied: number }>("/transactions/review/apply", {
    method: "POST",
    body: JSON.stringify(decisions),
  });

export const deleteTransaction = async (id: string): Promise<void> => {
  const res = await apiFetch(`/api/transactions/${id}`, { method: "DELETE" });
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
  const res = await apiFetch("/api/imports", { method: "POST", body: form });
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

export const confirmImport = (id: string, decisions: ReviewDecisions) =>
  request<ImportBatchView>(`/imports/${id}/confirm`, {
    method: "POST",
    body: JSON.stringify(decisions),
  });

export const discardImport = async (id: string): Promise<void> => {
  const res = await apiFetch(`/api/imports/${id}`, { method: "DELETE" });
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

/** One proposed income schedule; the review screen edits amount and day. */
export interface OnboardingIncome {
  name: string;
  payer: string | null;
  amount_cents: number;
  pattern: "monthly" | "some_months";
  months: number[] | null;
  day: number | null;
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
  income?: OnboardingIncome[];
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
  income?: IncomeScheduleIn[];
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

// ---- Coach conversation (coach-conversation) -------------------------------------

export interface FuturePaymentData {
  category_id: string;
  category_name: string;
  icon: string;
  name: string;
  due_month: string;
  target_cents: number;
  saved_cents: number;
  percent: number;
  plan_monthly_cents: number;
  needed_monthly_cents: number;
  assigned_cents: number;
  contributions_left: number;
  on_track: boolean;
  /** What this month's assignment lacks to reach the needed amount. */
  gap_cents: number;
}

export interface CoachPreviewCategory {
  category_id: string;
  name: string;
  assigned_before_cents: number;
  assigned_after_cents: number;
  available_before_cents: number;
  available_after_cents: number;
}

export interface CoachActionPreview {
  kind: CoachAction["kind"];
  month: string;
  title: string;
  categories: CoachPreviewCategory[];
  /** Absent on category choices (they move no money). */
  to_be_assigned_before_cents: number;
  to_be_assigned_after_cents: number;
  accounts_unchanged: boolean;
  error: { code: string } | null;
  /** Payment kinds only: the payment in words and its effect on the category. */
  payment?: {
    name: string | null;
    sentence_before: string | null;
    sentence_after: string | null;
    next_due_month: string | null;
    estimated: boolean;
    category_id: string;
  };
  amounts?: {
    normal_before_cents: number;
    normal_after_cents: number;
    catch_up_before_cents: number;
    catch_up_after_cents: number;
  };
  /** Expected-income kinds only: the income in words and its effect on the plan. */
  income?: { sentence_before: string | null; sentence_after: string | null; estimated: boolean };
  plan?: {
    month_expected_before_cents: number;
    month_expected_after_cents: number;
    year_expected_before_cents: number;
    year_expected_after_cents: number;
    income_known_before: boolean;
    income_known_after: boolean;
    gap_before_cents: number | null;
    gap_after_cents: number | null;
  };
  link?: {
    amount_cents: number;
    occurrence_before: { name: string; status: string; received_cents: number } | null;
    occurrence_after: { name: string; status: string; received_cents: number } | null;
    unplanned_before: boolean;
    unplanned_after: boolean;
  };
  /** Debt kinds only: the debt's plan and the paydown before and after. */
  debt?: {
    before: CoachDebtRow | null;
    after: CoachDebtRow | null;
    debt_free_before: string | null;
    debt_free_after: string | null;
    total_owed_before_cents: number;
    total_owed_after_cents: number;
    extra_before_cents: number;
    extra_after_cents: number;
    extra_target: string | null;
    cushion_note: boolean;
    cushion_suggested_cents: number;
  };
  /** Category choices only. */
  name?: string;
  similar?: { id: string; name: string; group_id: string; group_name: string; reason: string }[];
  groups?: { id: string; name: string }[];
  suggested_group_id?: string | null;
  follow_up_title?: string | null;
  transaction?: {
    amount_cents: number;
    direction: "expense" | "income";
    category_name: string | null;
    payee: string | null;
    date: string;
    account_name: string | null;
    note: string | null;
  };
}

export interface CoachDebtRow {
  name: string;
  kind: "card" | "loan" | "personal";
  position: number | null;
  end_month: string | null;
  required_monthly_cents: number;
  below_minimum: boolean | null;
  monthly_interest_cents: number | null;
  text: string;
}

export interface CoachAction {
  id: string;
  kind:
    | "transaction"
    | "assignment"
    | "assignments"
    | "moves"
    | "category"
    | "payment"
    | "payment_update"
    | "payment_delete"
    | "income"
    | "income_update"
    | "income_delete"
    | "income_link"
    | "debt"
    | "debt_update"
    | "debt_delete"
    | "debt_extra"
    | "debt_convert";
  /** resolved: a category choice answered with an existing category. */
  status: "proposed" | "applied" | "stale" | "cancelled" | "undone" | "resolved";
  title: string;
  /** The typed command (ids): Edit sends a changed copy back. */
  command: {
    month: string;
    moves?: { from_category_id: string | null; from_name: string | null; to_category_id: string; to_name: string; amount_cents: number }[];
    items?: { category_id: string; category_name: string; amount_cents: number }[];
    category_id?: string | null;
    amount_cents?: number;
    direction?: "expense" | "income";
    payee?: string | null;
    date?: string;
    account_id?: string | null;
    note?: string | null;
  };
  preview: CoachActionPreview;
  revision: string;
  result: Record<string, unknown> | null;
  created_at: string;
  applied_at: string | null;
  undone_at: string | null;
  can_undo: boolean;
}

interface WidgetBase<T extends string, D> {
  type: T;
  schema_version: number;
  snapshot_version: string | null;
  computed_at: string;
  data: D;
}

export type CoachWidget =
  | WidgetBase<"month_summary", Pick<HomeView, "month" | "status" | "reasons" | "summary" | "future">>
  | WidgetBase<"breakdown", { summary: HomeSummary }>
  | WidgetBase<"future_payment", FuturePaymentData>
  | WidgetBase<"action_preview", { action_id: string; action: CoachAction }>
  | WidgetBase<"action_result", { action_id: string; title: string; action: CoachAction }>
  | WidgetBase<"category_choice", { action_id: string; action: CoachAction }>
  | WidgetBase<"coach_proposal", CoachProposal>
  | WidgetBase<"transaction", {
      id: string;
      date: string;
      amount_cents: number;
      payee: string | null;
      category_name: string | null;
      account_name: string | null;
      description: string | null;
    }>;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  widgets: CoachWidget[];
  client_message_id: string | null;
  reply_to: string | null;
  created_at: string;
}

export interface ConversationView {
  /** Oldest first. */
  messages: ChatMessage[];
  has_more: boolean;
}

export const fetchConversation = (before?: string) =>
  request<ConversationView>(`/coach/conversation${before ? `?before=${encodeURIComponent(before)}` : ""}`);

/** The coach couldn't answer (503 coach_unavailable); the message is kept. */
export class CoachUnavailableError extends Error {
  constructor(readonly userMessage: ChatMessage | null) {
    super("coach_unavailable");
  }
}

export async function sendCoachMessage(
  text: string,
  clientMessageId: string,
): Promise<{ user_message: ChatMessage; reply: ChatMessage }> {
  const res = await apiFetch("/api/coach/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, client_message_id: clientMessageId }),
  });
  const body = await res.json().catch(() => null);
  if (res.status === 503 && body?.detail?.code === "coach_unavailable") {
    throw new CoachUnavailableError(body.detail.user_message ?? null);
  }
  if (!res.ok) throw new ApiError(body?.detail?.code ?? body?.code ?? "unknown_error", res.status);
  return body;
}

export interface CoachActionIn {
  kind: "transaction" | "assignment" | "assignments" | "moves";
  moves?: { from_category_id: string | null; to_category_id: string; amount_cents: number }[];
  items?: { category_id: string; amount_cents: number }[];
  category_id?: string | null;
  amount_cents?: number;
  direction?: "expense" | "income";
  payee?: string | null;
  date?: string;
  account_id?: string | null;
  note?: string | null;
  /** A proposed action this one replaces (Edit). */
  replaces?: string;
}

export const createCoachAction = (body: CoachActionIn) =>
  request<CoachAction>("/coach/actions", { method: "POST", body: JSON.stringify(body) });

/** The numbers changed since the preview (409 action_stale): carries a
    fresh preview to review instead. */
export class ActionStaleError extends Error {
  constructor(readonly action: CoachAction) {
    super("action_stale");
  }
}

/** A category choice's answer when creating: the picked group or a new one. */
export type GroupChoice = { group_id: string } | { new_group_name: string };

export async function commitCoachAction(
  id: string,
  revision: string,
  idempotencyKey: string,
  choice?: GroupChoice,
): Promise<{ action: CoachAction; message: ChatMessage | null; follow_up?: CoachAction | null }> {
  const res = await apiFetch(`/api/coach/actions/${encodeURIComponent(id)}/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ revision, idempotency_key: idempotencyKey, ...choice }),
  });
  const body = await res.json().catch(() => null);
  if (res.status === 409 && body?.detail?.code === "action_stale") {
    throw new ActionStaleError(body.detail.action as CoachAction);
  }
  if (!res.ok) throw new ApiError(body?.detail?.code ?? body?.code ?? "unknown_error", res.status);
  return body;
}

/** "Use X" on a category choice: nothing is created; the pending step is
    proposed with X. */
export const resolveCategoryChoice = (id: string, categoryId: string) =>
  request<{ action: CoachAction; follow_up: CoachAction | null }>(
    `/coach/actions/${encodeURIComponent(id)}/resolve`,
    { method: "POST", body: JSON.stringify({ category_id: categoryId }) },
  );

export const cancelCoachAction = (id: string) =>
  request<CoachAction>(`/coach/actions/${encodeURIComponent(id)}/cancel`, { method: "POST" });

export const undoCoachAction = (id: string) =>
  request<CoachAction>(`/coach/actions/${encodeURIComponent(id)}/undo`, { method: "POST" });

export const fetchCoachActions = () => request<CoachAction[]>("/coach/actions?status=applied,undone");
