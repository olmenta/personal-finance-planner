"""The payment in words (coach-payments-setup design D3): the same outputs as
the webapp's `describe` in webapp/src/lib/schedules.ts."""

import pytest

from app.services.payment_text import describe

CASES = [
    ({"amount_cents": 85000, "pattern": "monthly", "day": 1}, "850,00 € every month, day 1"),
    ({"amount_cents": 4000, "pattern": "monthly"}, "40,00 € every month"),
    ({"amount_cents": 12000, "pattern": "monthly", "count": 12, "start_month": "2026-11"},
     "120,00 € every month · 12 payments from November 2026"),
    ({"amount_cents": 63200, "pattern": "some_months", "months": [9, 10, 11, 12, 1, 2, 3, 4, 5, 6], "day": 5},
     "632,00 € from September to June, day 5"),
    ({"amount_cents": 5000, "pattern": "some_months", "months": [7]}, "50,00 € in July"),
    ({"amount_cents": 5000, "pattern": "some_months", "months": [3, 7, 11]}, "50,00 € in Mar, Jul, Nov"),
    ({"amount_cents": 5000, "pattern": "some_months", "months": list(range(1, 13))}, "50,00 € every month"),
    ({"amount_cents": 60000, "pattern": "annual", "month": 2}, "600,00 € once a year, in February"),
    ({"amount_cents": 12000, "pattern": "every_n", "every_n": 3, "start_month": "2026-11", "estimated": True},
     "120,00 € every 3 months from November 2026 (estimated)"),
    ({"amount_cents": 200000, "pattern": "once", "once_month": "2028-05"}, "2.000,00 € once, in May 2028"),
    ({"amount_cents": 120000, "pattern": "no_date"}, "1.200,00 € a year, no fixed date"),
]


@pytest.mark.parametrize(("fields", "text"), CASES)
def test_describe(fields, text):
    assert describe(fields) == text
