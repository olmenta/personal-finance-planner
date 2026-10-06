"""Category-suggestion suite: labeled bank rows against the default tree.
Measures category accuracy and payee normalization."""

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.ingestion import NormalizedTransaction
from app.services import category_suggestions
from app.services.category_setup import DEFAULT_CATEGORY_TREE

CATEGORIES = [
    SimpleNamespace(id=name, name=name, group=SimpleNamespace(name=group), payment_account_id=None)
    for group, items in DEFAULT_CATEGORY_TREE
    for name, _icon in items
]


@dataclass
class Row:
    description: str
    amount_cents: int


@dataclass
class Expected:
    category: str | None  # None = should stay uncategorized (income)
    payee: str | None


LABELED: list[tuple[str, Row, Expected]] = [
    ("mercadona", Row("COMPRA TARJ. 4188 MERCADONA VALENCIA", -4520), Expected("Supermercado", "Mercadona")),
    ("lidl", Row("PAGO CON TARJETA LIDL SUPERMERCADOS 0231", -2315), Expected("Supermercado", "Lidl")),
    ("repsol", Row("REPSOL ESTACION SERVICIO E.S. 2231", -6000), Expected("Gasolina", "Repsol")),
    ("metro", Row("METRO DE MADRID RECARGA TARJETA", -1220), Expected("Transporte público", "Metro de Madrid")),
    ("iberdrola", Row("RECIBO IBERDROLA CLIENTES SAU", -6837), Expected("Suministros", "Iberdrola")),
    ("netflix", Row("NETFLIX.COM 866-579-7172", -1399), Expected("Suscripciones", "Netflix")),
    ("restaurant", Row("TPV RESTAURANTE CASA PACO MADRID", -3850), Expected("Restaurantes", None)),
    ("rent", Row("TRANSFERENCIA ALQUILER PISO OCTUBRE", -85000), Expected("Alquiler", None)),
    ("cinema", Row("CINES YELMO PALAFOX ENTRADAS", -1800), Expected("Ocio", "Yelmo Cines")),
    ("salary", Row("NOMINA ACME SOFTWARE SL", 235000), Expected(None, "Acme Software")),
]


def task(row: Row) -> dict:
    normalized = NormalizedTransaction(
        date=date(2026, 10, 1), amount_cents=row.amount_cents, currency="EUR",
        description=row.description, category_hint=None,
    )
    suggestion = category_suggestions.suggest(CATEGORIES, [normalized])[0]
    return {"category": suggestion.category_id, "payee": suggestion.payee, "confidence": suggestion.confidence}


@dataclass
class CategoryMatches(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return ctx.output["category"] == ctx.expected_output.category


@dataclass
class PayeeNormalized(Evaluator):
    """The cleaned payee names the expected merchant (case-insensitive, any word order)."""

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        want = ctx.expected_output.payee
        if want is None:
            return {}
        # Same words in any order ("Cines Yelmo" = "Yelmo Cines"); legal
        # suffixes like SL/SA don't count against it.
        got = set((ctx.output["payee"] or "").casefold().replace(".", "").split()) - {"sl", "sa", "sau"}
        return {"payee_normalized": set(want.casefold().split()) <= got}


def dataset() -> Dataset:
    return Dataset(
        name="category_suggestions",
        cases=[Case(name=name, inputs=row, expected_output=exp) for name, row, exp in LABELED],
        evaluators=[CategoryMatches(), PayeeNormalized()],
    )
