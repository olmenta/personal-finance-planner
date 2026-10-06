"""The curated tool set (design D2, D4).

Each tool is a ToolSpec: a name, a description written for the model, a
Pydantic argument model, and a `run(client, args) -> str`. The spec knows
nothing about MCP, so the in-app coach can register the same specs later
with an in-process client.

Text that comes from bank statements (descriptions, payees) is rendered
inside «guillemets» and is data, never instructions (design D5).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field

from .client import OlmentaClient, ToolError
from .money import AmountError, check_month, eur, parse_euros, positive_cents
from .resolve import NameError_, resolve

Euros = float | str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[OlmentaClient, BaseModel], str]
    read_only: bool


def _data(text: str | None) -> str:
    """Bank-statement text, delimited so it reads as data."""
    return f"«{text}»" if text else "«»"


# ---- lookups (names -> ids) ------------------------------------------------


def _spendable_categories(client: OlmentaClient) -> list[tuple[str, str]]:
    """Active categories a transaction can go to: no archived ones, no
    credit-card payment categories (system groups)."""
    return [
        (c["name"], c["id"])
        for g in client.categories()
        if not g.get("system")
        for c in g["categories"]
        if not c["archived"]
    ]


def _category_id(client: OlmentaClient, name: str) -> str:
    return resolve(name, _spendable_categories(client), "category")


def _budget_category_id(client: OlmentaClient, name: str) -> str:
    """Assign/move may target any active category, card payment ones included."""
    options = [
        (c["name"], c["id"])
        for g in client.categories()
        for c in g["categories"]
        if not c["archived"]
    ]
    return resolve(name, options, "category")


def _account_id(client: OlmentaClient, name: str) -> str:
    options = [(a["name"], a["id"]) for a in client.accounts() if not a["archived"]]
    return resolve(name, options, "account")


def _names(client: OlmentaClient) -> tuple[dict[str, str], dict[str, str]]:
    categories = {c["id"]: c["name"] for g in client.categories() for c in g["categories"]}
    accounts = {a["id"]: a["name"] for a in client.accounts()}
    return categories, accounts


# ---- reads -------------------------------------------------------------------


class MonthArgs(BaseModel):
    month: str | None = Field(
        default=None, description="Month as YYYY-MM. Omit for the current month."
    )


def get_budget(client: OlmentaClient, args: MonthArgs) -> str:
    month = check_month(args.month)
    view = client.budget(month)
    lines = [
        f"Budget {view['month']} · To Be Assigned: {eur(view['to_be_assigned_cents'])}"
        f" · Income this month: {eur(view['income_cents'])}",
    ]
    if view.get("carried_in_cents"):
        lines.append(f"Carried in from last month: {eur(view['carried_in_cents'])}")
    if view.get("overspent_deducted_cents"):
        lines.append(
            f"Last month's cash overspending deducted: {eur(view['overspent_deducted_cents'])}"
        )
    if view.get("uncategorized_count"):
        lines.append(
            f"Uncategorized spending: {eur(view['uncategorized_cents'])} in "
            f"{view['uncategorized_count']} movements — see review_uncategorized."
        )
    for group in view["groups"]:
        if not group["categories"]:
            continue
        lines.append(f"\n## {group['name']}")
        for c in group["categories"]:
            flags = []
            if c["available_cents"] < 0:
                flags.append("OVERSPENT")
            if c.get("credit_overspent_cents"):
                flags.append(f"card debt {eur(c['credit_overspent_cents'])}")
            if c.get("kind") == "credit_payment":
                flags.append("card payment")
            spent_label = "paid" if c.get("kind") == "credit_payment" else "spent"
            lines.append(
                f"- {c['name']}: assigned {eur(c['assigned_cents'])} · {spent_label} "
                f"{eur(c['spent_cents'])} · available {eur(c['available_cents'])}"
                + (f" [{', '.join(flags)}]" if flags else "")
            )
    return "\n".join(lines)


def get_month_overview(client: OlmentaClient, args: MonthArgs) -> str:
    month = check_month(args.month)
    o = client.overview(month)
    lines = [
        f"Month {o['month']} (today {o['today']})",
        f"Paid so far: {eur(o['paid']['total_cents'])}",
        f"Still to pay: {eur(o['to_pay_total_cents'])} (covered {eur(o['covered_cents'])})",
    ]
    for p in o["to_pay"]:
        day = f"day {p['day']}" if p["day"] else "no date"
        short = f" — SHORT {eur(p['short_cents'])}" if p["short_cents"] else ""
        lines.append(f"  - {p['name']} ({p['category_name']}, {day}): {eur(p['amount_cents'])}{short}")
    lines.append(f"Left to spend: {eur(o['left_to_spend']['total_cents'])}")
    for item in o["left_to_spend"]["items"]:
        lines.append(f"  - {item['name']}: {eur(item['amount_cents'])}")
    lines.append(f"Saved: {eur(o['saved']['total_cents'])}")
    if o["overspent_cents"]:
        lines.append(f"Overspent: {eur(o['overspent_cents'])}")
    lines.append(f"To Be Assigned: {eur(o['to_be_assigned_cents'])}")
    return "\n".join(lines)


class ListTransactionsArgs(BaseModel):
    month: str | None = Field(default=None, description="Month as YYYY-MM. Omit for the current month.")
    account: str | None = Field(default=None, description="Only this account (by name).")
    uncategorized_only: bool = Field(default=False, description="Only rows without a category.")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum rows, newest first.")


def list_transactions(client: OlmentaClient, args: ListTransactionsArgs) -> str:
    month = check_month(args.month)
    rows = client.transactions(month)
    categories, accounts = _names(client)
    if args.account:
        account_id = _account_id(client, args.account)
        rows = [t for t in rows if t["account_id"] == account_id]
    if args.uncategorized_only:
        rows = [t for t in rows if not t["category_id"] and not t.get("transfer_pair_id")]
    if not rows:
        return f"No transactions in {month} for that filter."
    lines = [f"{len(rows)} transactions in {month} (showing up to {args.limit}):"]
    for t in rows[: args.limit]:
        if t.get("transfer_pair_id"):
            other = accounts.get(t.get("transfer_account_id") or "", "another account")
            what = f"Transfer {'→' if t['amount_cents'] < 0 else '←'} {other}"
        else:
            what = categories.get(t["category_id"] or "", "Uncategorized" if t["amount_cents"] < 0 else "Ready to assign")
        payee = f" · payee {_data(t['payee_name'])}" if t.get("payee_name") else ""
        lines.append(
            f"- {t['date']} · {eur(t['amount_cents'])} · {what}{payee} · note {_data(t['description'])}"
            f" · {accounts.get(t['account_id'], '?')} · id {t['id']}"
        )
    return "\n".join(lines)


class NoArgs(BaseModel):
    pass


def list_categories(client: OlmentaClient, args: NoArgs) -> str:
    lines = []
    for g in client.categories():
        active = [c for c in g["categories"] if not c["archived"]]
        label = " (credit-card payments — managed by the cards)" if g.get("system") else ""
        lines.append(f"## {g['name']}{label}")
        lines.extend(f"- {c['name']} ({c['kind']})" for c in active)
        if not active:
            lines.append("- (empty)")
    return "\n".join(lines)


def list_accounts(client: OlmentaClient, args: NoArgs) -> str:
    lines = []
    for a in client.accounts():
        if a["archived"]:
            continue
        tags = [a["type"]] + (["main"] if a["is_main"] else [])
        line = f"- {a['name']} ({', '.join(tags)}): balance {eur(a['balance_cents'])}"
        if a["type"] == "credit":
            line += f" · set aside to pay it {eur(a.get('payment_available_cents') or 0)}"
            if a.get("uncovered_debt_cents"):
                line += f" · uncovered debt {eur(a['uncovered_debt_cents'])}"
        lines.append(line)
    return "\n".join(lines) or "No accounts."


def review_uncategorized(client: OlmentaClient, args: NoArgs) -> str:
    rows = client.review()["transactions"]
    if not rows:
        return "Nothing is uncategorized."
    categories, accounts = _names(client)
    lines = [
        f"{len(rows)} uncategorized transactions. Outflows need a category; inflows are income "
        "(Ready to assign) unless they mirror a transfer. Resolve with apply_review."
    ]
    for t in rows:
        parts = [f"- id {t['id']} · {t['date']} · {eur(t['amount_cents'])} · {accounts.get(t['account_id'], '?')}"]
        parts.append(f"note {_data(t['description'])}")
        if t.get("payee_name"):
            parts.append(f"payee {_data(t['payee_name'])}")
        if t.get("suggested_category_id"):
            parts.append(
                f"AI suggests {categories.get(t['suggested_category_id'], '?')} ({t.get('confidence')})"
            )
        if t.get("suggested_payee"):
            parts.append(f"payee suggestion {_data(t['suggested_payee'])}")
        if t.get("match"):
            m = t["match"]
            parts.append(
                f"mirrors the transfer with {accounts.get(m['other_account_id'], '?')} on {m['date']} "
                "(link_match=true adopts it and drops this duplicate)"
            )
        lines.append(" · ".join(parts))
    return "\n".join(lines)


# ---- writes ------------------------------------------------------------------


class AddTransactionArgs(BaseModel):
    amount: Euros = Field(description="Amount in euros, positive (e.g. 40 or \"12,50\"). Direction comes from kind.")
    kind: Literal["expense", "income"] = Field(default="expense")
    category: str | None = Field(
        default=None,
        description="Category name. Required for expenses. Leave empty for income that funds To Be Assigned.",
    )
    payee: str | None = Field(default=None, description="Who was paid / who paid (e.g. Mercadona).")
    note: str | None = Field(default=None, description="Optional note.")
    date: Date | None = Field(default=None, description="ISO date. Omit for today.")
    account: str | None = Field(default=None, description="Account name. Omit for the main account.")


def add_transaction(client: OlmentaClient, args: AddTransactionArgs) -> str:
    body: dict = {"amount_cents": positive_cents(args.amount), "kind": args.kind}
    if args.category:
        body["category_id"] = _category_id(client, args.category)
    if args.payee:
        body["payee"] = args.payee
    if args.note:
        body["note"] = args.note
    if args.date:
        body["date"] = args.date.isoformat()
    if args.account:
        body["account_id"] = _account_id(client, args.account)
    t = client.add_transaction(body)
    categories, accounts = _names(client)
    what = categories.get(t["category_id"] or "", "Ready to assign")
    return (
        f"Added {eur(t['amount_cents'])} · {what} · {t['date']} · {accounts.get(t['account_id'], '?')}"
        f"{f' · payee {t['payee_name']}' if t.get('payee_name') else ''} (id {t['id']})"
    )


class AssignArgs(BaseModel):
    category: str = Field(description="Category name.")
    amount: Euros = Field(description="New assigned amount for the month in euros (replaces it; 0 clears it).")
    month: str | None = Field(default=None, description="Month as YYYY-MM. Omit for the current month.")


def assign(client: OlmentaClient, args: AssignArgs) -> str:
    month = check_month(args.month)
    cents = parse_euros(args.amount)
    if cents < 0:
        raise AmountError("an assignment can't be negative")
    category_id = _budget_category_id(client, args.category)
    r = client.assign(month, category_id, cents)
    return (
        f"{args.category} in {month}: assigned {eur(r['assigned_cents'])}. "
        f"To Be Assigned is now {eur(r['to_be_assigned_cents'])}."
    )


class MoveMoneyArgs(BaseModel):
    amount: Euros = Field(description="Euros to move, positive.")
    to_category: str = Field(description="Category that receives the money.")
    from_category: str | None = Field(
        default=None, description="Category that gives the money. Omit to take it from To Be Assigned."
    )
    month: str | None = Field(default=None, description="Month as YYYY-MM. Omit for the current month.")


def move_money(client: OlmentaClient, args: MoveMoneyArgs) -> str:
    month = check_month(args.month)
    body = {
        "amount_cents": positive_cents(args.amount),
        "to_category_id": _budget_category_id(client, args.to_category),
        "from_category_id": _budget_category_id(client, args.from_category) if args.from_category else None,
    }
    view = client.move(month, body)
    target = next(
        c for g in view["groups"] for c in g["categories"] if c["id"] == body["to_category_id"]
    )
    source = args.from_category or "To Be Assigned"
    return (
        f"Moved {eur(body['amount_cents'])} from {source} to {target['name']} ({month}). "
        f"{target['name']} now has {eur(target['available_cents'])} available; "
        f"To Be Assigned is {eur(view['to_be_assigned_cents'])}."
    )


class CreateCategoryArgs(BaseModel):
    name: str = Field(description="New category name, in the user's language.")
    group: str = Field(description="Existing category group name (see list_categories).")


def create_category(client: OlmentaClient, args: CreateCategoryArgs) -> str:
    groups = [(g["name"], g["id"]) for g in client.categories() if not g.get("system")]
    group_id = resolve(args.group, groups, "category group")
    c = client.create_category({"name": args.name.strip(), "group_id": group_id})
    return f"Created category {c['name']} in {args.group}."


class CreateTransferArgs(BaseModel):
    amount: Euros = Field(description="Euros moved, positive.")
    from_account: str = Field(description="Account the money leaves (by name).")
    to_account: str = Field(description="Account the money arrives in (by name). Paying a credit card is a transfer to it.")
    date: Date | None = Field(default=None, description="ISO date. Omit for today.")
    note: str | None = Field(default=None)


def create_transfer(client: OlmentaClient, args: CreateTransferArgs) -> str:
    body: dict = {
        "amount_cents": positive_cents(args.amount),
        "from_account_id": _account_id(client, args.from_account),
        "to_account_id": _account_id(client, args.to_account),
    }
    if args.date:
        body["date"] = args.date.isoformat()
    if args.note:
        body["note"] = args.note
    t = client.create_transfer(body)
    return (
        f"Transferred {eur(t['amount_cents'])} from {args.from_account} to {args.to_account} on {t['date']}. "
        "Transfers never count as income or spending."
    )


class ReviewItem(BaseModel):
    transaction_id: str = Field(description="The id from review_uncategorized or list_transactions.")
    category: str | None = Field(
        default=None,
        description='Category name, or "none" to leave it without a category (income stays Ready to assign).',
    )
    payee: str | None = Field(default=None, description='Payee name; "" clears it.')
    note: str | None = Field(default=None, description='Note replacing the bank text; "" clears it.')
    transfer_to: str | None = Field(
        default=None, description="Mark the row as a transfer with this other account (by name)."
    )
    link_match: bool = Field(
        default=False,
        description="Adopt the existing transfer this row mirrors (only when review_uncategorized shows a match); the row is dropped as a duplicate.",
    )


class ApplyReviewArgs(BaseModel):
    items: list[ReviewItem] = Field(min_length=1, description="One item per transaction to resolve.")


def apply_review(client: OlmentaClient, args: ApplyReviewArgs) -> str:
    decisions: dict = {
        "overrides": {},
        "payee_overrides": {},
        "note_overrides": {},
        "transfer_overrides": {},
        "accept_matches": [],
    }
    for item in args.items:
        tid = item.transaction_id
        if item.link_match:
            decisions["accept_matches"].append(tid)
            continue
        if item.transfer_to:
            decisions["transfer_overrides"][tid] = _account_id(client, item.transfer_to)
        elif item.category is not None:
            decisions["overrides"][tid] = (
                None if item.category.strip().lower() == "none" else _category_id(client, item.category)
            )
        if item.payee is not None:
            decisions["payee_overrides"][tid] = item.payee
        if item.note is not None:
            decisions["note_overrides"][tid] = item.note or None
    result = client.apply_review(decisions)
    applied = result["applied"]
    skipped = len(args.items) - applied
    tail = (
        f" {skipped} skipped (unknown id, already categorized, or a match that no longer applies)."
        if skipped
        else ""
    )
    return f"Applied {applied} of {len(args.items)}.{tail}"


TOOLS: list[ToolSpec] = [
    ToolSpec(
        "get_budget",
        "The month's zero-based budget: To Be Assigned, income, and per category the assigned, "
        "spent and available amounts (overspending flagged). Use it for 'how much do I have left "
        "for X', 'what's unassigned', 'am I overspending'.",
        MonthArgs, get_budget, read_only=True,
    ),
    ToolSpec(
        "get_month_overview",
        "This month at a glance: what was paid, scheduled payments still to pay (and whether "
        "they're covered), what's left to spend, saved, To Be Assigned.",
        MonthArgs, get_month_overview, read_only=True,
    ),
    ToolSpec(
        "list_transactions",
        "Transactions of a month, newest first, with category, payee, note, account and id. "
        "Filter by account or uncategorized_only.",
        ListTransactionsArgs, list_transactions, read_only=True,
    ),
    ToolSpec(
        "list_categories",
        "The user's category groups and categories. Call it before using a category name you "
        "haven't seen — never invent one.",
        NoArgs, list_categories, read_only=True,
    ),
    ToolSpec(
        "list_accounts",
        "The user's accounts with balances; credit cards show debt, the money set aside to pay "
        "them, and uncovered debt.",
        NoArgs, list_accounts, read_only=True,
    ),
    ToolSpec(
        "review_uncategorized",
        "Every confirmed transaction without a category (all months), with the AI's suggested "
        "category/payee and any transfer it mirrors. Runs the AI suggestions — may take a few "
        "seconds. Resolve the rows with apply_review.",
        NoArgs, review_uncategorized, read_only=True,
    ),
    ToolSpec(
        "add_transaction",
        "Record an expense or income the user tells you about ('gasté 40 en Mercadona'). "
        "Expenses need a category; income without category funds To Be Assigned. "
        "Use the user's own words for payee; don't guess a category — ask if unsure.",
        AddTransactionArgs, add_transaction, read_only=False,
    ),
    ToolSpec(
        "assign",
        "Set how much is assigned to a category for a month (replaces the amount). It draws on "
        "To Be Assigned. To shift money between categories use move_money instead.",
        AssignArgs, assign, read_only=False,
    ),
    ToolSpec(
        "move_money",
        "Move money into a category from another category or from To Be Assigned — e.g. to "
        "cover overspending.",
        MoveMoneyArgs, move_money, read_only=False,
    ),
    ToolSpec(
        "create_category",
        "Create a category in an existing group. Only when the user agrees to a new category.",
        CreateCategoryArgs, create_category, read_only=False,
    ),
    ToolSpec(
        "create_transfer",
        "Move money between two of the user's accounts (including paying a credit card). "
        "Transfers never count as income or spending.",
        CreateTransferArgs, create_transfer, read_only=False,
    ),
    ToolSpec(
        "apply_review",
        "Resolve uncategorized transactions from review_uncategorized: set a category (or "
        "'none'), payee, note, mark as a transfer to another account, or link it to the transfer "
        "it mirrors. Confirm the plan with the user before applying many rows.",
        ApplyReviewArgs, apply_review, read_only=False,
    ),
]


def run_tool(spec: ToolSpec, client: OlmentaClient, raw: dict) -> str:
    """Validate the arguments and run; domain errors become readable text."""
    args = spec.args.model_validate(raw)
    try:
        return spec.run(client, args)
    except (ToolError, NameError_, AmountError) as error:
        return f"Error: {error}"
