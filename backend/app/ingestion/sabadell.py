"""Banco Sabadell legacy `.xls` export adapter.

Layout (single sheet): preamble rows (account, holder, date range), then a
header row
    F. Operativa | Concepto | F. Valor | Importe | Saldo | Referencia 1 | Referencia 2
xlrd 2.x reads only legacy `.xls` — exactly what Sabadell exports.
"""

from typing import Any

import xlrd

from .base import (
    NormalizedTransaction,
    StatementFormatError,
    cell_text,
    parse_amount_cents,
    parse_date,
)

_REQUIRED = ("f. operativa", "concepto", "importe")


class SabadellXlsAdapter:
    source = "import_sabadell"

    def parse(self, content: bytes) -> list[NormalizedTransaction]:
        try:
            book = xlrd.open_workbook(file_contents=content)
        except Exception as exc:
            raise StatementFormatError() from exc
        for sheet in book.sheets():
            rows = [
                [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                for r in range(sheet.nrows)
            ]
            parsed = self._parse_rows(rows)
            if parsed is not None:
                return parsed
        raise StatementFormatError()

    def _parse_rows(self, rows: list[list[Any]]) -> list[NormalizedTransaction] | None:
        header_index, columns = _find_header(rows)
        if columns is None:
            return None
        transactions: list[NormalizedTransaction] = []
        for row in rows[header_index + 1 :]:
            cells = {name: row[i] if i < len(row) else None for name, i in columns.items()}
            if not cell_text(cells.get("f_operativa")) and not cell_text(cells.get("importe")):
                continue
            description = cell_text(cells.get("concepto"))
            balance_cents = _optional_cents(cells.get("saldo"))
            transactions.append(
                NormalizedTransaction(
                    date=parse_date(cells.get("f_operativa")),
                    amount_cents=parse_amount_cents(cells.get("importe")),
                    currency="EUR",  # per-account currency lives in the preamble
                    description=description,
                    external_ref=f"{description}|bal:{balance_cents}"
                    if balance_cents is not None
                    else None,
                    raw_payload={k: cell_text(v) for k, v in cells.items() if v is not None},
                )
            )
        return transactions


def _find_header(rows: list[list[Any]]) -> tuple[int, dict[str, int] | None]:
    for index, row in enumerate(rows):
        names = [cell_text(c).lower() for c in row]
        if all(any(n.startswith(req) for n in names) for req in _REQUIRED):
            columns: dict[str, int] = {}
            for position, name in enumerate(names):
                if name.startswith("f. operativa"):
                    columns["f_operativa"] = position
                elif name.startswith("concepto"):
                    columns["concepto"] = position
                elif name.startswith("f. valor"):
                    columns["f_valor"] = position
                elif name.startswith("importe"):
                    columns["importe"] = position
                elif name.startswith("saldo"):
                    columns["saldo"] = position
                elif name.startswith("referencia 1"):
                    columns["referencia_1"] = position
                elif name.startswith("referencia 2"):
                    columns["referencia_2"] = position
            if {"f_operativa", "concepto", "importe"} <= columns.keys():
                return index, columns
    return -1, None


def _optional_cents(value: Any) -> int | None:
    if value is None or cell_text(value) == "":
        return None
    try:
        return parse_amount_cents(value)
    except StatementFormatError:
        return None
