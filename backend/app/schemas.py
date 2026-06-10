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
    note: str | None = Field(default=None, max_length=500)
    date: date_type | None = None


class TransactionOut(BaseModel):
    id: str
    account_id: str
    category_id: str | None
    date: date_type
    amount_cents: int  # signed: expenses negative, income positive
    currency: str
    description: str | None
    source: str
    status: str

    model_config = {"from_attributes": True}


# ---- Categories -------------------------------------------------------------


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


class ErrorOut(BaseModel):
    code: str
