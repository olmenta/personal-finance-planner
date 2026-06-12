"""Pydantic request/response schemas.

BudgetMonthView mirrors the webapp contract (webapp/src/lib/mock-data.ts).
Errors carry machine-readable codes (§6.7): {"code": "<snake_case>"}.
"""

from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field

# ---- Transactions ----------------------------------------------------------


class TransactionCreate(BaseModel):
    amount_cents: int = Field(gt=0)
    category_id: str
    kind: Literal["expense", "income"] = "expense"
    # Find-or-create against the user's payees, case-insensitive on the
    # trimmed name (spec: payees). Empty/whitespace-only means "no payee".
    payee: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    date: date_type | None = None


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

    model_config = {"from_attributes": True}


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
    category_id: str | None = None  # None = leave category untouched
    # None = leave payee untouched; "" clears it; name resolves find-or-create.
    payee: str | None = Field(default=None, max_length=120)


class ApplyCategoriesRequest(BaseModel):
    # txn_id -> accepted assignment
    assignments: dict[str, CategoryAssignment]


class ApplyCategoriesResponse(BaseModel):
    applied: int


# ---- Imports ----------------------------------------------------------------


class ImportBatchView(BaseModel):
    id: str
    account_id: str
    source: str
    filename: str
    status: Literal["staged", "confirmed", "discarded"]
    row_count: int
    skipped_duplicates: int
    transactions: list[TransactionOut]


class ConfirmImportRequest(BaseModel):
    # txn_id -> category_id (null clears the suggestion)
    overrides: dict[str, str | None] = Field(default_factory=dict)
    # txn_id -> payee name ("" clears; resolves find-or-create on confirm)
    payee_overrides: dict[str, str] = Field(default_factory=dict)


# ---- Payees -----------------------------------------------------------------


class PayeeOut(BaseModel):
    id: str
    name: str
    # Category of the user's most recent confirmed transaction with this
    # payee — the autocomplete prefill memory (design D3). Null when none.
    last_category_id: str | None


# ---- Categories -------------------------------------------------------------


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Any lucide name ≤40 chars; unknown names degrade to a circle in the UI
    # (design D3) so the backend doesn't hard-code the icon list.
    icon: str = Field(default="circle", min_length=1, max_length=40)
    group_id: str


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, min_length=1, max_length=40)
    group_id: str | None = None
    archived: bool | None = None


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

    model_config = {"from_attributes": True}


class CategoryGroupOut(BaseModel):
    id: str
    name: str
    sort_order: int
    categories: list[CategoryOut]

    model_config = {"from_attributes": True}


# ---- Budget month view ------------------------------------------------------


class BudgetCategoryView(BaseModel):
    id: str
    name: str
    icon: str
    assigned_cents: int
    spent_cents: int
    rollover_cents: int
    available_cents: int
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
    to_be_assigned_cents: int
    groups: list[BudgetGroupView]


class AssignRequest(BaseModel):
    amount_cents: int = Field(ge=0)


class AssignResponse(BaseModel):
    category_id: str
    assigned_cents: int
    suggestion_state: str
    to_be_assigned_cents: int


class ConfirmSuggestionsRequest(BaseModel):
    category_ids: list[str]


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


class ErrorOut(BaseModel):
    code: str
