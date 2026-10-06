"""Core persistence models (project-definition §6.4, v1 subset).

All monetary amounts are signed integer cents; currency fixed to EUR in v1.
Derived values (available, to_be_assigned) are computed in services, never stored.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    auth0_sub: Mapped[str | None] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    locale: Mapped[str] = mapped_column(String(8), default="es")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # cash | bank | credit — credit balances are naturally negative (debt).
    type: Mapped[str] = mapped_column(String(16), default="cash")
    institution: Mapped[str | None] = mapped_column(String(120))
    # Hidden from pickers; its transactions keep counting (no account delete).
    archived: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Credit only: day of the month the card is charged to the bank (1–31).
    payment_day: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CategoryGroup(Base):
    __tablename__ = "category_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # System-managed (e.g. "Tarjetas de crédito"): not deletable/renamable by CRUD.
    system: Mapped[bool] = mapped_column(default=False, server_default="false")

    categories: Mapped[list["Category"]] = relationship(back_populates="group")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("category_groups.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(40), default="circle")
    archived: Mapped[bool] = mapped_column(default=False)
    # Stored flag: "savings" when the user marks the category as savings,
    # "flexible" otherwise. The effective kind is derived (see `effective_kind`):
    # any payment schedule makes the category "scheduled".
    kind: Mapped[str] = mapped_column(String(12), default="flexible", server_default="flexible")
    # Set on a credit card's system payment category ("Pago <card>").
    payment_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), unique=True
    )

    group: Mapped[CategoryGroup] = relationship(back_populates="categories")
    schedules: Mapped[list["PaymentSchedule"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="PaymentSchedule.created_at"
    )

    @property
    def savings(self) -> bool:
        return self.kind == "savings"

    @property
    def effective_kind(self) -> str:
        if self.schedules:
            return "scheduled"
        return "savings" if self.savings else "flexible"


class PaymentSchedule(Base):
    """When a category's money is actually due (category-targets design D2).

    One row per payment; pattern-specific columns are nullable and validated
    per pattern at the API. Amounts are never derived here — normal and
    catch-up monthly amounts are computed on read (services/schedules.py).
    """

    __tablename__ = "payment_schedules"
    __table_args__ = (Index("ix_payment_schedules_user_category", "user_id", "category_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int] = mapped_column(Integer)
    # monthly | some_months | annual | every_n | once | no_date
    pattern: Mapped[str] = mapped_column(String(12))
    months: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))  # some_months
    month: Mapped[int | None] = mapped_column(Integer)  # annual
    every_n: Mapped[int | None] = mapped_column(Integer)  # every_n
    start_month: Mapped[str | None] = mapped_column(String(7))  # every_n; monthly with count
    count: Mapped[int | None] = mapped_column(Integer)  # monthly, finite
    once_month: Mapped[str | None] = mapped_column(String(7))  # once
    day: Mapped[int | None] = mapped_column(Integer)
    estimated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    category: Mapped["Category"] = relationship(back_populates="schedules")


class Payee(Base):
    """Who was paid (expense) / who paid (income) — one entity, label-only split.

    Born from transaction writes (find-or-create), never via its own endpoint.
    """

    __tablename__ = "payees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("uq_payees_user_lower_name", "user_id", func.lower(name), unique=True),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    source: Mapped[str] = mapped_column(String(24))  # import_bbva | import_sabadell
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(12), default="staged")  # staged | confirmed | discarded
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "dedupe_hash", name="uq_txn_account_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    payee_id: Mapped[str | None] = mapped_column(ForeignKey("payees.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Signed cents: expenses negative, income positive (§6.3 ingestion contract).
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    description: Mapped[str | None] = mapped_column(String(500))
    # manual | import_bbva | import_sabadell | import_custom | opening_balance
    source: Mapped[str] = mapped_column(String(24), default="manual")
    import_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.id"), index=True
    )
    dedupe_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="confirmed")  # staged | confirmed
    # Shared by the two twin rows of a transfer (design D1); NULL otherwise.
    transfer_pair_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # selectin: payee_name ships on every listed row (TransactionOut) without N+1.
    payee: Mapped[Payee | None] = relationship(lazy="selectin")

    # Not a column: the other twin's account, filled in by readers that
    # render transfers (see services/transfers.annotate_counterparts).
    transfer_account_id = None  # str | None

    @property
    def payee_name(self) -> str | None:
        return self.payee.name if self.payee else None


class OnboardingSession(Base):
    """One AI onboarding interview run (project-definition §6.6).

    Transcript and extracted answers persist per turn so the interview
    survives reloads; the generated setup proposal is stored on completion
    so the review screen can be re-rendered. JSONB columns are reassigned
    (never mutated in place) so change tracking fires.
    """

    __tablename__ = "onboarding_sessions"
    __table_args__ = (
        # One active interview per user — concurrent /start calls (e.g. React
        # StrictMode double-firing in dev) must not fork the conversation.
        Index(
            "uq_onboarding_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | completed | abandoned
    transcript_json: Mapped[list] = mapped_column(JSONB, default=list)
    extracted_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    proposal_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserPreferences(Base):
    """Per-user preferences memory — one JSONB document, written only through
    PreferencesStore (§6.6). Feeds category generation, import suggestions,
    and future coach features.
    """

    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    prompt_version: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class BudgetMonth(Base):
    __tablename__ = "budget_months"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_budget_user_month"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"

    assignments: Mapped[list["BudgetAssignment"]] = relationship(back_populates="budget_month")


class BudgetAssignment(Base):
    __tablename__ = "budget_assignments"
    __table_args__ = (
        UniqueConstraint("budget_month_id", "category_id", name="uq_assignment_month_category"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    budget_month_id: Mapped[str] = mapped_column(ForeignKey("budget_months.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    assigned_cents: Mapped[int] = mapped_column(Integer, default=0)
    # draft (proposed, unconfirmed) | confirmed (accepted) | edited (user changed)
    suggestion_state: Mapped[str] = mapped_column(String(12), default="draft")
    suggestion_cents: Mapped[int | None] = mapped_column(Integer)

    budget_month: Mapped[BudgetMonth] = relationship(back_populates="assignments")


class LlmUsage(Base):
    """One model call's usage and cost (llm-layer design D3). Content-free
    by design: no prompt, no output, no ids of the user's financial data —
    only what per-user cost caps and route tuning need."""

    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    route: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micro_eur: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    # ok | error | fallback
    outcome: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
