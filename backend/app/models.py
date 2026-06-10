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
    Integer,
    String,
    UniqueConstraint,
)
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
    type: Mapped[str] = mapped_column(String(16), default="cash")  # cash | bank
    institution: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CategoryGroup(Base):
    __tablename__ = "category_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    categories: Mapped[list["Category"]] = relationship(back_populates="group")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("category_groups.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(40), default="circle")
    archived: Mapped[bool] = mapped_column(default=False)

    group: Mapped[CategoryGroup] = relationship(back_populates="categories")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "dedupe_hash", name="uq_txn_account_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Signed cents: expenses negative, income positive (§6.3 ingestion contract).
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    description: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(24), default="manual")
    import_batch_id: Mapped[str | None] = mapped_column(String(36))
    dedupe_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="confirmed")  # staged | confirmed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


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
