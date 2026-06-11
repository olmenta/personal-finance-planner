"""Ingestion port: normalized contract + shared defensive cell parsing.

Bank exports are messy and drift without notice. Adapters map their layout to
NormalizedTransaction; the import pipeline never sees bank-specific shapes.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol


class StatementFormatError(Exception):
    """Raised when a file doesn't match the adapter's expected layout."""

    def __init__(self, code: str = "file_format_unrecognized") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NormalizedTransaction:
    date: date
    amount_cents: int  # signed: expenses negative, income positive
    currency: str
    description: str
    external_ref: str | None = None
    # Free-text category from the source (custom CSV template); fed to the
    # suggestion model as a hint — never required to match the category list.
    category_hint: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class TransactionSource(Protocol):
    """Port for transaction ingestion (§6.3)."""

    source: str  # persisted on Transaction.source / ImportBatch.source

    def parse(self, content: bytes) -> list[NormalizedTransaction]:
        """Return normalized rows or raise StatementFormatError."""
        ...


def parse_amount_cents(value: Any) -> int:
    """Excel amounts are usually floats; defensively accept es-ES strings.

    "1.234,56" → 123456; -23.27 → -2327.
    """
    if value is None:
        raise StatementFormatError()
    if isinstance(value, (int, float, Decimal)):
        quantity = Decimal(str(value))
    else:
        text = str(value).strip().replace("\xa0", "").replace("€", "").strip()
        if not text:
            raise StatementFormatError()
        if "," in text:
            # es-ES: "." thousands, "," decimal ("1.234,56").
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") > 1 or (("." in text) and len(text.rsplit(".", 1)[1]) == 3):
            # Dots only and 3-digit groups: es thousands ("1.234" → 1234).
            text = text.replace(".", "")
        # Otherwise a single dot with 1-2 decimals is a plain decimal point.
        try:
            quantity = Decimal(text)
        except InvalidOperation as exc:
            raise StatementFormatError() from exc
    return int((quantity * 100).to_integral_value())


def parse_date(value: Any) -> date:
    """DD/MM/YYYY strings are the norm; ISO dates and date-typed cells too."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise StatementFormatError()


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
