"""Custom CSV template adapter — the escape hatch for any other bank.

The user fills the downloadable template (webapp/public/import-template.csv)
manually from their bank's export. Required columns: date, amount,
description. Optional: category (free text → category_hint for the LLM) and
balance (running balance → dedupe discriminator, like the bank adapters).
"""

import csv
import io

from .base import (
    NormalizedTransaction,
    StatementFormatError,
    cell_text,
    parse_amount_cents,
    parse_date,
)

_REQUIRED = {"date", "amount", "description"}
_OPTIONAL = {"category", "balance"}


class CustomCsvAdapter:
    source = "import_custom"

    def parse(self, content: bytes) -> list[NormalizedTransaction]:
        text = _decode(content)
        delimiter = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [row for row in reader if any(cell_text(c) for c in row)]
        if not rows:
            raise StatementFormatError()

        headers = [cell_text(h).lower() for h in rows[0]]
        if not _REQUIRED <= set(headers):
            raise StatementFormatError()
        columns = {name: headers.index(name) for name in _REQUIRED | (_OPTIONAL & set(headers))}

        transactions: list[NormalizedTransaction] = []
        for row in rows[1:]:
            cells = {name: row[i] if i < len(row) else "" for name, i in columns.items()}
            description = cell_text(cells["description"])
            hint = cell_text(cells.get("category", ""))
            balance = cell_text(cells.get("balance", ""))
            balance_cents = parse_amount_cents(balance) if balance else None
            transactions.append(
                NormalizedTransaction(
                    date=parse_date(cells["date"]),
                    amount_cents=parse_amount_cents(cells["amount"]),
                    currency="EUR",
                    description=description,
                    external_ref=f"{description}|bal:{balance_cents}"
                    if balance_cents is not None
                    else None,
                    category_hint=hint or None,
                    raw_payload={k: cell_text(v) for k, v in cells.items() if cell_text(v)},
                )
            )
        return transactions


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")
