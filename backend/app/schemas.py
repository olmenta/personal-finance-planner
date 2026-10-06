"""Pydantic request/response schemas.

BudgetMonthView mirrors the webapp contract (webapp/src/lib/mock-data.ts).
Errors carry machine-readable codes (§6.7): {"code": "<snake_case>"}.
"""

from datetime import date as date_type
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---- Transactions ----------------------------------------------------------


class TransactionCreate(BaseModel):
    amount_cents: int = Field(gt=0)
    # Required for expenses; optional for income (income funds To Be Assigned,
    # it doesn't have to live in a spending category).
    category_id: str | None = None
    kind: Literal["expense", "income"] = "expense"
    # Find-or-create against the user's payees, case-insensitive on the
    # trimmed name (spec: payees). Empty/whitespace-only means "no payee".
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    date: date_type | None = None
    # Omitted = the user's main account (oldest active).
    account_id: str | None = None


class TransactionUpdate(BaseModel):
    """Partial edit of a confirmed transaction (design D1).

    Omitted fields stay unchanged — handlers must consult `model_fields_set`
    for fields where None is meaningful (`note: null` clears the description;
    `payee: ""` clears the payee).
    """

    amount_cents: int | None = Field(default=None, gt=0)
    kind: Literal["expense", "income"] | None = None
    category_id: str | None = None
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    date: date_type | None = None
    # Moves the row between registers.
    account_id: str | None = None


class TransactionOut(BaseModel):
    id: str
    account_id: str
    category_id: str | None
    payee_id: str | None
    payee_name: str | None  # joined server-side; AI-resolved at import staging
    date: date_type
    amount_cents: int  # signed: expenses negative, income positive
    currency: str
    description: str | None
    source: str
    status: str
    # Transfer twins share a pair id; transfer_account_id is the other side's
    # account (null for ordinary rows).
    transfer_pair_id: str | None = None
    transfer_account_id: str | None = None

    model_config = {"from_attributes": True}


# ---- Accounts (spec: accounts-api, credit-cards) ------------------------------

AccountType = Literal["cash", "bank", "credit"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: AccountType = "bank"
    institution: str | None = Field(default=None, max_length=120)
    # Signed: positive cash on hand; negative pre-existing card debt.
    opening_balance_cents: int | None = None
    payment_day: int | None = Field(default=None, ge=1, le=31)  # credit only


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    institution: str | None = Field(default=None, max_length=120)
    archived: bool | None = None
    payment_day: int | None = Field(default=None, ge=1, le=31)  # null clears


class AccountOut(BaseModel):
    id: str
    name: str
    type: AccountType
    institution: str | None
    archived: bool
    balance_cents: int  # derived: sum of confirmed transactions
    is_main: bool
    # Credit accounts only (null otherwise).
    payment_day: int | None = None
    suggested_payment_day: int | None = None
    payment_category_id: str | None = None
    payment_available_cents: int | None = None
    uncovered_debt_cents: int | None = None


# ---- Transfers (spec: transfers) ---------------------------------------------


class TransferCreate(BaseModel):
    from_account_id: str
    to_account_id: str
    amount_cents: int = Field(gt=0)
    date: date_type | None = None
    note: str | None = Field(default=None, max_length=500)


class TransferUpdate(BaseModel):
    """Mirrored edit; `note: null` clears it, absent leaves it."""

    amount_cents: int | None = Field(default=None, gt=0)
    date: date_type | None = None
    note: str | None = Field(default=None, max_length=500)


class TransferOut(BaseModel):
    pair_id: str
    from_account_id: str
    to_account_id: str
    amount_cents: int
    date: date_type
    note: str | None
    out_transaction_id: str
    in_transaction_id: str


# ---- Imports ----------------------------------------------------------------


class TwinMatch(BaseModel):
    """An existing confirmed transfer twin a staged row seems to mirror —
    a non-binding suggestion (design D5)."""

    transaction_id: str
    pair_id: str
    other_account_id: str  # where the transfer came from / went to
    date: date_type


class StagedTransactionOut(TransactionOut):
    match: TwinMatch | None = None


class ImportBatchView(BaseModel):
    id: str
    account_id: str
    source: str
    filename: str
    status: Literal["staged", "confirmed", "discarded"]
    row_count: int
    skipped_duplicates: int
    transactions: list[StagedTransactionOut]


class ConfirmImportRequest(BaseModel):
    # txn_id -> category_id (null clears the suggestion)
    overrides: dict[str, str | None] = Field(default_factory=dict)
    # txn_id -> payee name ("" clears; resolves find-or-create on confirm)
    payee_overrides: dict[str, str] = Field(default_factory=dict)
    # txn_id -> note, which replaces the bank description (null or "" clears).
    note_overrides: dict[str, Annotated[str, Field(max_length=500)] | None] = Field(
        default_factory=dict
    )
    # txn_id -> other account: the row is a transfer, its twin is created on
    # confirm (wins over a category override for the same row).
    transfer_overrides: dict[str, str] = Field(default_factory=dict)
    # Staged rows whose match suggestion was accepted: the existing twin is
    # adopted and the staged row dropped.
    accept_matches: list[str] = Field(default_factory=list)


# ---- Review of uncategorized transactions (spec: transaction-review) --------


class ReviewRowOut(StagedTransactionOut):
    """A confirmed uncategorized row with the AI's suggestion as a default —
    never stored until the user applies it (design D3)."""

    suggested_category_id: str | None = None
    suggested_payee: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None


class ReviewView(BaseModel):
    transactions: list[ReviewRowOut]


class ReviewApplyRequest(ConfirmImportRequest):
    """The import's decision maps, applied to confirmed uncategorized rows."""


class ReviewApplyResponse(BaseModel):
    applied: int  # rows written


# ---- Payees -----------------------------------------------------------------


class PayeeOut(BaseModel):
    id: str
    name: str
    # Category of the user's most recent confirmed transaction with this
    # payee — the autocomplete prefill memory (design D3). Null when none.
    last_category_id: str | None


# ---- Categories -------------------------------------------------------------


CategoryKind = Literal["flexible", "scheduled", "savings"]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Any lucide name ≤40 chars; unknown names degrade to a circle in the UI
    # (design D3) so the backend doesn't hard-code the icon list.
    icon: str = Field(default="circle", min_length=1, max_length=40)
    group_id: str
    # Marks the category as savings (shown as saved, never as spendable).
    # Categories with payments are "scheduled" automatically.
    savings: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, min_length=1, max_length=40)
    group_id: str | None = None
    archived: bool | None = None
    savings: bool | None = None


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    sort_order: int | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    icon: str
    archived: bool
    # Derived: scheduled (has payments) | savings (flag) | flexible.
    kind: CategoryKind = Field(validation_alias="effective_kind")
    savings: bool
    # Set on a credit card's system payment category.
    payment_account_id: str | None = None

    model_config = {"from_attributes": True}


class CategoryGroupOut(BaseModel):
    id: str
    name: str
    sort_order: int
    system: bool = False  # "Tarjetas de crédito": not editable via CRUD
    categories: list[CategoryOut]

    model_config = {"from_attributes": True}


# ---- Payment schedules ------------------------------------------------------
# One model per pattern (category-targets design D2); the API validates the
# body against this union and answers 422 invalid_schedule otherwise.

MonthStr = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class _ScheduleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount_cents: int = Field(gt=0)
    day: int | None = Field(default=None, ge=1, le=31)
    estimated: bool = False

    model_config = {"extra": "forbid"}


class MonthlySchedule(_ScheduleBase):
    pattern: Literal["monthly"]
    count: int | None = Field(default=None, ge=1, le=600)
    start_month: MonthStr | None = None

    @model_validator(mode="after")
    def _count_needs_start(self) -> "MonthlySchedule":
        if self.count is not None and self.start_month is None:
            raise ValueError("count requires start_month")
        return self


class SomeMonthsSchedule(_ScheduleBase):
    pattern: Literal["some_months"]
    months: list[Annotated[int, Field(ge=1, le=12)]] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _unique_months(self) -> "SomeMonthsSchedule":
        if len(set(self.months)) != len(self.months):
            raise ValueError("months must be unique")
        self.months = sorted(self.months)
        return self


class AnnualSchedule(_ScheduleBase):
    pattern: Literal["annual"]
    month: int = Field(ge=1, le=12)


class EveryNSchedule(_ScheduleBase):
    pattern: Literal["every_n"]
    every_n: int = Field(ge=2, le=12)
    start_month: MonthStr


class OnceSchedule(_ScheduleBase):
    pattern: Literal["once"]
    once_month: MonthStr


class NoDateSchedule(_ScheduleBase):
    pattern: Literal["no_date"]


ScheduleIn = Annotated[
    MonthlySchedule
    | SomeMonthsSchedule
    | AnnualSchedule
    | EveryNSchedule
    | OnceSchedule
    | NoDateSchedule,
    Field(discriminator="pattern"),
]

SCHEDULE_FIELDS = (
    "name", "amount_cents", "pattern", "months", "month", "every_n",
    "start_month", "count", "once_month", "day", "estimated",
)


# ---- Income schedules -------------------------------------------------------
# Same rule models as payments (income-schedules design D2) plus a payer name,
# resolved to a payee on write (D3). No `no_date`: undated income can't be
# planned, so it fails discriminator validation → 422 invalid_schedule.


class _Payer(BaseModel):
    payer: str | None = Field(default=None, max_length=120)

    @field_validator("payer")
    @classmethod
    def _trim_payer(cls, value: str | None) -> str | None:
        trimmed = (value or "").strip()
        return trimmed or None


class IncomeMonthlySchedule(MonthlySchedule, _Payer):
    pass


class IncomeSomeMonthsSchedule(SomeMonthsSchedule, _Payer):
    pass


class IncomeAnnualSchedule(AnnualSchedule, _Payer):
    pass


class IncomeEveryNSchedule(EveryNSchedule, _Payer):
    pass


class IncomeOnceSchedule(OnceSchedule, _Payer):
    pass


IncomeScheduleIn = Annotated[
    IncomeMonthlySchedule
    | IncomeSomeMonthsSchedule
    | IncomeAnnualSchedule
    | IncomeEveryNSchedule
    | IncomeOnceSchedule,
    Field(discriminator="pattern"),
]


class IncomeScheduleOut(BaseModel):
    id: str
    name: str
    amount_cents: int
    payee_id: str | None
    payer: str | None
    pattern: Literal["monthly", "some_months", "annual", "every_n", "once"]
    months: list[int] | None
    month: int | None
    every_n: int | None
    start_month: str | None
    count: int | None
    once_month: str | None
    day: int | None
    estimated: bool
    yearly_cents: int  # Σ of its occurrences over the next 12 months

    model_config = {"from_attributes": True}


IncomeStatus = Literal["received", "pending", "late", "missed"]


class IncomeOccurrence(BaseModel):
    schedule_id: str
    name: str
    payee_id: str | None
    payer: str | None
    day: int | None
    amount_cents: int
    estimated: bool
    received_cents: int
    difference_cents: int | None  # received − expected; null unless received
    status: IncomeStatus
    transaction_ids: list[str]


class UnplannedIncome(BaseModel):
    transaction_id: str
    payee_id: str | None
    label: str  # payee name, else the description
    date: date_type
    amount_cents: int


class MonthIncomeView(BaseModel):
    month: str
    has_schedules: bool
    occurrences: list[IncomeOccurrence]
    unplanned: list[UnplannedIncome]
    expected_cents: int
    received_cents: int
    still_expected_cents: int


class ScheduleOut(BaseModel):
    id: str
    category_id: str
    name: str
    amount_cents: int
    pattern: Literal["monthly", "some_months", "annual", "every_n", "once", "no_date"]
    months: list[int] | None
    month: int | None
    every_n: int | None
    start_month: str | None
    count: int | None
    once_month: str | None
    day: int | None
    estimated: bool
    debt_id: str | None = None  # managed from "What you owe" (spec: payment-schedules)

    model_config = {"from_attributes": True}


# ---- Budget month view ------------------------------------------------------


class CoverSuggestion(BaseModel):
    # null = cover from To Be Assigned
    source_category_id: str | None
    amount_cents: int


class BudgetCategoryView(BaseModel):
    id: str
    name: str
    icon: str
    # credit_payment: a card's payment category (spent = payments to the card).
    kind: CategoryKind | Literal["credit_payment"]
    payment_account_id: str | None = None
    # Computed from payment schedules; null when the category has none.
    normal_cents: int | None = None
    catch_up_cents: int | None = None
    assigned_cents: int
    spent_cents: int
    rollover_cents: int
    available_cents: int
    overspent_cents: int
    # Last month's overspending of this category, reset instead of carried
    # (deducted from To Be Assigned).
    rollover_reset_cents: int
    # Card spending this month not covered by the category's available: it
    # stays as card debt instead of moving to the payment category.
    credit_overspent_cents: int = 0
    cover_suggestion: CoverSuggestion | None = None
    suggestion_cents: int | None
    suggestion_state: Literal["draft", "confirmed", "edited"]
    # Quick-fill sources for the assignment UI; null when no history exists.
    last_month_assigned_cents: int | None
    avg_3m_cents: int | None
    last_month_spent_cents: int | None


class BudgetGroupView(BaseModel):
    id: str
    name: str
    sort_order: int
    categories: list[BudgetCategoryView]


class BudgetMonthView(BaseModel):
    month: str
    income_cents: int
    # Cumulative: carried_in + unbudgeted − assigned − overspent_deducted.
    to_be_assigned_cents: int
    carried_in_cents: int  # previous month's To Be Assigned
    overspent_deducted_cents: int  # previous month's uncovered cash overspending
    # The month's outflows still waiting for a category (any account; not
    # transfers or opening balances). Reported only — no other figure moves.
    uncategorized_cents: int = 0
    uncategorized_count: int = 0
    groups: list[BudgetGroupView]


class AssignRequest(BaseModel):
    amount_cents: int = Field(ge=0)


class AssignResponse(BaseModel):
    category_id: str
    assigned_cents: int
    suggestion_state: str
    to_be_assigned_cents: int


class MoveRequest(BaseModel):
    # null = draw from To Be Assigned
    from_category_id: str | None
    to_category_id: str
    amount_cents: int = Field(gt=0)


class ConfirmSuggestionsRequest(BaseModel):
    category_ids: list[str]


# ---- Month overview ("Este mes") and plan -------------------------------------


class OverviewPaidItem(BaseModel):
    category_id: str
    category_name: str
    name: str | None  # schedule name; null = the category's other spending
    day: int | None
    amount_cents: int


class OverviewAmountItem(BaseModel):
    category_id: str
    name: str
    group: str
    amount_cents: int
    spent_cents: int | None = None


class OverviewPaidSection(BaseModel):
    total_cents: int
    items: list[OverviewPaidItem]


class OverviewAmountSection(BaseModel):
    total_cents: int
    items: list[OverviewAmountItem]


class OverviewPending(BaseModel):
    category_id: str
    category_name: str
    schedule_id: str
    name: str
    day: int | None
    amount_cents: int
    covered_cents: int
    short_cents: int
    estimated: bool
    late: bool = False  # a required debt payment more than 3 days past its day


class OverviewView(BaseModel):
    month: str
    today: date_type
    paid: OverviewPaidSection
    to_pay: list[OverviewPending]
    to_pay_total_cents: int
    covered_cents: int
    left_to_spend: OverviewAmountSection
    saved: OverviewAmountSection
    overspent_cents: int
    to_be_assigned_cents: int
    # accounts = covered + left_to_spend + saved + to_be_assigned − overspent
    accounts_cents: int


class UpcomingOccurrence(BaseModel):
    category_id: str
    category_name: str
    schedule_id: str
    name: str
    day: int | None
    amount_cents: int
    estimated: bool
    covered: bool | None = None  # null when expected income is unknown
    short_cents: int | None = None


class UpcomingMonth(BaseModel):
    month: str
    expected_income_cents: int | None = None  # null when no income schedules
    occurrences: list[UpcomingOccurrence]
    payments_cents: int
    short_cents: int | None = None
    flexible_budget_cents: int | None = None
    flexible_funded_cents: int | None = None
    set_aside_wanted_cents: int | None = None
    set_aside_funded_cents: int | None = None
    unassigned_cents: int | None = None


class UpcomingView(BaseModel):
    income_known: bool
    income_cents: int | None  # Σ expected income over the 12 months
    months: list[UpcomingMonth]


class PlanSummary(BaseModel):
    month: str
    income_known: bool
    income_cents: int | None  # Σ income-schedule occurrences in the window
    scheduled_cents: int
    flexible_cents: int
    goals_cents: int
    costs_cents: int
    gap_cents: int | None
    gap_monthly_cents: int | None


# ---- Month summary (dashboard) ----------------------------------------------


class SummaryWeek(BaseModel):
    start: date_type  # bucket's first day, clamped to the month
    spent_cents: int
    income_cents: int


class SummaryView(BaseModel):
    month: str
    balance_cents: int  # all-time sum of confirmed transactions
    income_cents: int
    expense_cents: int
    weeks: list[SummaryWeek]


# ---- Onboarding ------------------------------------------------------------


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class OnboardingStatusOut(BaseModel):
    has_completed: bool
    has_active: bool


class OnboardingSessionOut(BaseModel):
    id: str
    status: str
    prompt_version: str
    # Turn entries: {role, content} for user turns; assistant turns add
    # input_kind, options, done so the webapp can re-render the pending turn.
    transcript: list[dict]
    proposal: dict | None = None


class OnboardingCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    icon: str = Field(default="circle", max_length=40)


class OnboardingGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    categories: list[OnboardingCategoryIn] = []


class OnboardingAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["bank", "credit"] = "bank"


class OnboardingFinalizeRequest(BaseModel):
    """The reviewed proposal: checked items only, renames applied,
    user-added entries included."""

    accounts: list[OnboardingAccountIn] = []
    category_groups: list[OnboardingGroupIn] = []
    payers: list[str] = []
    payees: list[str] = []
    # The reviewed income schedules (income-schedules): created at finalize.
    income: list[IncomeScheduleIn] = []


class OnboardingFinalizeResponse(BaseModel):
    categories_created: int
    payees_created: int


class ErrorOut(BaseModel):
    code: str


# ---- Debts (spec: debts) ----------------------------------------------------

RatePeriod = Literal["month", "year"]


class _DebtRate(BaseModel):
    rate_bp: int | None = Field(default=None, ge=0, le=100_000)
    rate_period: RatePeriod | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _rate_needs_period(self):
        if self.rate_bp is not None and self.rate_period is None:
            raise ValueError("rate_bp requires rate_period")
        return self


class CardDebtIn(_DebtRate):
    kind: Literal["card"]
    account_id: str
    plan_monthly_cents: int | None = Field(default=None, gt=0)
    target_month: MonthStr | None = None
    minimum_cents: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _one_plan(self):
        if (self.plan_monthly_cents is None) == (self.target_month is None):
            raise ValueError("give plan_monthly_cents or target_month")
        return self


class LoanDebtIn(_DebtRate):
    kind: Literal["loan"]
    name: str = Field(min_length=1, max_length=120)
    installment_cents: int = Field(gt=0)
    installments_left: int = Field(ge=1, le=600)
    next_month: MonthStr
    day: int | None = Field(default=None, ge=1, le=31)


class PersonalDebtIn(_DebtRate):
    kind: Literal["personal"]
    name: str = Field(min_length=1, max_length=120)
    owed_cents: int = Field(gt=0)
    due_month: MonthStr | None = None
    lender: str | None = Field(default=None, max_length=120)


DebtIn = Annotated[CardDebtIn | LoanDebtIn | PersonalDebtIn, Field(discriminator="kind")]


class DebtUpdate(BaseModel):
    """Partial edit; fields that don't apply to the debt's kind → 422."""

    rate_bp: int | None = Field(default=None, ge=0, le=100_000)
    rate_period: RatePeriod | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # card
    plan_monthly_cents: int | None = Field(default=None, gt=0)
    target_month: MonthStr | None = None
    minimum_cents: int | None = Field(default=None, gt=0)
    # loan
    installment_cents: int | None = Field(default=None, gt=0)
    installments_left: int | None = Field(default=None, ge=1, le=600)
    next_month: MonthStr | None = None
    day: int | None = Field(default=None, ge=1, le=31)
    # personal
    owed_cents: int | None = Field(default=None, gt=0)
    due_month: MonthStr | None = None
    lender: str | None = Field(default=None, max_length=120)

    model_config = {"extra": "forbid"}


class DebtExtraIn(BaseModel):
    extra_monthly_cents: int = Field(ge=0)


class ConvertToLoanIn(BaseModel):
    installment_cents: int = Field(gt=0)
    installments_left: int = Field(ge=1, le=600)
    next_month: MonthStr
    day: int | None = Field(default=None, ge=1, le=31)
    rate_bp: int | None = Field(default=None, ge=0, le=100_000)
    rate_period: RatePeriod | None = None

    model_config = {"extra": "forbid"}


class DebtOut(BaseModel):
    id: str
    kind: Literal["card", "loan", "personal"]
    category_id: str
    account_id: str | None  # card only
    name: str
    lender: str | None
    owed_cents: int
    rate_bp: int | None
    rate_period: RatePeriod | None
    monthly_rate_bp: float | None  # normalized monthly rate
    minimum_cents: int | None
    below_minimum: bool | None
    required_monthly_cents: int  # this month's required payment (0 when optional)
    plan_monthly_cents: int | None  # card plan
    installment_cents: int | None  # loan
    installments_left: int | None  # loan
    next_month: str | None  # loan: first unpaid installment
    day: int | None
    due_month: str | None  # personal
    end_month: str | None  # null: doesn't end within the horizon
    paid_off: bool
    position: int | None  # 1-based paydown order; null when paid off
    monthly_interest_cents: int | None  # only with a known rate


class DebtCushion(BaseModel):
    suggested_cents: int
    saved_cents: int


class DebtsView(BaseModel):
    debts: list[DebtOut]
    total_owed_cents: int
    extra_monthly_cents: int
    extra_target_debt_id: str | None
    debt_free_month: str | None
    cushion: DebtCushion
