"""Euros in, cents inside, es-ES out — the tools never expose cents."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

# "1.234" / "12.345.678" — dots as thousands separators.
_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+$")


class AmountError(ValueError):
    pass


def parse_euros(value: float | int | str) -> int:
    """12.5 / "12,50" / "1.234,56" / "1234.56" / "12 €" -> integer cents."""
    if isinstance(value, bool):
        raise AmountError("amount must be a number of euros")
    if isinstance(value, (int, float)):
        cents = round(value * 100)
    else:
        text = value.strip().replace("€", "").replace(" ", "").replace(" ", "")
        text = text.lstrip("+")
        if "," in text and "." in text:
            # es-ES: dots group thousands, the comma is the decimal mark.
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        elif _THOUSANDS.match(text):
            text = text.replace(".", "")
        try:
            cents = round(float(text) * 100)
        except ValueError as error:
            raise AmountError(f"not an amount in euros: {value!r}") from error
    return int(cents)


def positive_cents(value: float | int | str) -> int:
    cents = parse_euros(value)
    if cents <= 0:
        raise AmountError("amount must be greater than zero (use kind for direction)")
    return cents


def eur(cents: int) -> str:
    """-123456 -> "−1.234,56 €" (es-ES, typographic minus)."""
    sign = "−" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"{sign}{grouped},{frac:02d} €"


def current_month() -> str:
    return datetime.now(MADRID).strftime("%Y-%m")


def check_month(month: str | None) -> str:
    if month is None:
        return current_month()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise AmountError(f"month must look like 2026-10, got {month!r}")
    return month
