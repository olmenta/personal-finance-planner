"""Pydantic request/response schemas.

BudgetMonthView mirrors the webapp contract (webapp/src/lib/mock-data.ts).
Errors carry machine-readable codes (§6.7): {"code": "<snake_case>"}.
"""

from datetime import date as date_type
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

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


# ---- AI categorization review (spec: category-suggestions) -------------------


class SuggestCategoriesRequest(BaseModel):
    # None = all confirmed uncategorized transactions (500 newest).
    transaction_ids: list[str] | None = None


class CategoryProposal(BaseModel):
    transaction_id: str
    category_id: str | None
    payee: str | None  # cleaned merchant/payer name, null when unclear
    confidence: Literal["high", "medium", "low"]


class SuggestCategoriesResponse(BaseModel):
    proposals: list[CategoryProposal]


class CategoryAssignment(BaseModel):
    # Absent = leave category untouched; explicit null clears it (un-marks a
    # refund so the inflow counts as income again).
    category_id: str | None = None
    # None = leave payee untouched; "" clears it; name resolves find-or-create.
    payee: str | None = Field(default=None, max_length=120)


class ApplyCategoriesRequest(BaseModel):
    # txn_id -> accepted assignment
    assignments: dict[str, CategoryAssignment]


class ApplyCategoriesResponse(BaseModel):
    applied: int


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
    income_cents: int | None
    months: list[UpcomingMonth]


class PlanSummary(BaseModel):
    month: str
    income_known: bool
    income_cents: int | None  # expected fixed income × 12
    scheduled_cents: int
    flexible_cents: int
    goals_cents: int
    costs_cents: int
    gap_cents: int | None
    gap_monthly_cents: int | None


class ExpectedIncome(BaseModel):
    expected_monthly_cents: int | None = Field(default=None, ge=0)


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


class OnboardingIncomeIn(BaseModel):
    sources: list[str] = []
    expected_monthly_cents: int | None = Field(default=None, ge=0)
    income_day: int | None = Field(default=None, ge=1, le=31)


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
    income: OnboardingIncomeIn | None = None


class OnboardingFinalizeResponse(BaseModel):
    categories_created: int
    payees_created: int


class ErrorOut(BaseModel):
    code: str
