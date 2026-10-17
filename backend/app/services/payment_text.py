"""A payment in words, for coach previews and tool results. Port of the
webapp's `describe` (webapp/src/lib/schedules.ts); English placeholder copy
like the other titles. Change both together: tests pin the same outputs."""

from .coach import eur

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SHORT = [m[:3] for m in MONTH_NAMES]


def month_label(month: str | None) -> str:
    if not month:
        return ""
    year, mon = (int(p) for p in month.split("-"))
    return f"{MONTH_NAMES[mon - 1]} {year}"


def _months_text(months: list[int]) -> str:
    chosen = set(months)
    if len(chosen) == 12:
        return "every month"
    # A run of consecutive months (wrapping over December) reads as a range.
    start = next((m for m in months if ((m + 10) % 12) + 1 not in chosen), None)
    if start is not None:
        end, n = start, 1
        while (end % 12) + 1 in chosen and n < len(chosen):
            end = (end % 12) + 1
            n += 1
        if n == len(chosen):
            if len(chosen) == 1:
                return f"in {MONTH_NAMES[start - 1]}"
            return f"from {MONTH_NAMES[start - 1]} to {MONTH_NAMES[end - 1]}"
    return "in " + ", ".join(MONTH_SHORT[m - 1] for m in sorted(months))


def describe(fields: dict) -> str:
    """"632,00 € from September to June, day 5"."""
    a = eur(fields["amount_cents"])
    day = f", day {fields['day']}" if fields.get("day") else ""
    match fields["pattern"]:
        case "monthly":
            count = fields.get("count")
            tail = f" · {count} payments from {month_label(fields.get('start_month'))}" if count else ""
            text = f"{a} every month{day}{tail}"
        case "some_months":
            text = f"{a} {_months_text(list(fields.get('months') or []))}{day}"
        case "annual":
            text = f"{a} once a year, in {MONTH_NAMES[(fields.get('month') or 1) - 1]}{day}"
        case "every_n":
            text = f"{a} every {fields.get('every_n')} months from {month_label(fields.get('start_month'))}{day}"
        case "once":
            text = f"{a} once, in {month_label(fields.get('once_month'))}{day}"
        case _:
            text = f"{a} a year, no fixed date"
    return text + (" (estimated)" if fields.get("estimated") else "")
