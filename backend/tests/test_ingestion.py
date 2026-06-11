"""Adapter tests over generated anonymized workbooks (no DB needed)."""

from datetime import date

import pytest

from app.ingestion import ADAPTERS, StatementFormatError
from app.ingestion.base import parse_amount_cents

from fixtures import bbva_xlsx, sabadell_xls


class TestBBVAXlsxAdapter:
    def test_rows_normalized(self):
        rows = ADAPTERS["bbva"].parse(bbva_xlsx())
        assert len(rows) == 6
        first = rows[0]
        assert first.date == date(2026, 6, 10)
        assert first.amount_cents == -2327
        assert first.currency == "EUR"
        assert first.description == "Supermercado genérico — Pago con tarjeta"

    def test_income_row_positive(self):
        rows = ADAPTERS["bbva"].parse(bbva_xlsx())
        nomina = rows[-1]
        assert nomina.amount_cents == 88129
        assert nomina.description.startswith("Abono de nómina")

    def test_same_day_identical_rows_have_distinct_refs(self):
        rows = ADAPTERS["bbva"].parse(bbva_xlsx())
        coffees = [r for r in rows if "Cafetería" in r.description]
        assert len(coffees) == 2
        assert coffees[0].external_ref != coffees[1].external_ref

    def test_sabadell_file_rejected(self):
        with pytest.raises(StatementFormatError) as err:
            ADAPTERS["bbva"].parse(sabadell_xls())
        assert err.value.code == "file_format_unrecognized"

    def test_garbage_rejected(self):
        with pytest.raises(StatementFormatError):
            ADAPTERS["bbva"].parse(b"not an excel file at all")


class TestSabadellXlsAdapter:
    def test_rows_normalized(self):
        rows = ADAPTERS["sabadell"].parse(sabadell_xls())
        assert len(rows) == 4
        first = rows[0]
        assert first.date == date(2026, 6, 9)
        assert first.amount_cents == -2454
        assert first.description == "COMPRA TARJ. 0000XXXXXXXX0000 Tienda online"
        assert first.external_ref is not None and "bal:3383" in first.external_ref

    def test_income_row_positive(self):
        rows = ADAPTERS["sabadell"].parse(sabadell_xls())
        transfer = next(r for r in rows if "TRANSFERENCIA" in r.description)
        assert transfer.amount_cents == 15000

    def test_bbva_file_rejected(self):
        with pytest.raises(StatementFormatError) as err:
            ADAPTERS["sabadell"].parse(bbva_xlsx())
        assert err.value.code == "file_format_unrecognized"

    def test_garbage_rejected(self):
        with pytest.raises(StatementFormatError):
            ADAPTERS["sabadell"].parse(b"\x00\x01\x02nonsense")


class TestAmountParsing:
    @pytest.mark.parametrize(
        ("value", "cents"),
        [
            (-23.27, -2327),
            (881.29, 88129),
            ("-1.234,56", -123456),
            ("12,49", 1249),
            (-100, -10000),
        ],
    )
    def test_floats_and_es_strings(self, value, cents):
        assert parse_amount_cents(value) == cents

    def test_unparseable_raises(self):
        with pytest.raises(StatementFormatError):
            parse_amount_cents("n/a")


CUSTOM_CSV = (
    "date,amount,description,category,balance\n"
    "15/05/2026,-12.30,Mercadona semanal,Supermercado,420.10\n"
    "2026-05-01,1850.00,Nómina mayo,,2300.00\n"
    "02/05/2026,-9.99,Spotify,Suscripciones,\n"
)


class TestCustomCsvAdapter:
    def test_rows_normalized(self):
        rows = ADAPTERS["custom"].parse(CUSTOM_CSV.encode("utf-8"))
        assert len(rows) == 3
        first = rows[0]
        assert first.amount_cents == -1230
        assert first.date.isoformat() == "2026-05-15"
        assert first.category_hint == "Supermercado"
        assert first.external_ref is not None and "bal:42010" in first.external_ref

    def test_iso_date_and_missing_hint(self):
        rows = ADAPTERS["custom"].parse(CUSTOM_CSV.encode("utf-8"))
        salary = rows[1]
        assert salary.date.isoformat() == "2026-05-01"
        assert salary.amount_cents == 185000
        assert salary.category_hint is None

    def test_missing_balance_means_no_ref(self):
        rows = ADAPTERS["custom"].parse(CUSTOM_CSV.encode("utf-8"))
        assert rows[2].external_ref is None

    def test_semicolon_delimiter_and_comma_decimals(self):
        csv_es = "date;amount;description\n15/05/2026;-12,30;Mercadona\n"
        rows = ADAPTERS["custom"].parse(csv_es.encode("latin-1"))
        assert rows[0].amount_cents == -1230

    def test_missing_required_column_rejected(self):
        bad = "date,description\n15/05/2026,Mercadona\n"
        with pytest.raises(StatementFormatError) as err:
            ADAPTERS["custom"].parse(bad.encode("utf-8"))
        assert err.value.code == "file_format_unrecognized"
