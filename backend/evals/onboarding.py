"""Onboarding interview suite: does each answer settle the expected fields,
and is a final proposal sound? Cases are synthetic conversations."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, LLMJudge

from app.llm import run_structured
from app.llm.agents import _model
from app.llm.routes import route_config
from app.services import onboarding

LOCALE = "es"


@dataclass
class Conversation:
    """The transcript so far; the last entry is the user's answer under test."""

    turns: list[tuple[str, str]]


def _ask(question: str, answer: str) -> Conversation:
    return Conversation(turns=[("assistant", question), ("user", answer)])


def interview_turn(conversation: Conversation) -> dict[str, Any]:
    config = onboarding.load_prompt_config()
    session = SimpleNamespace(
        transcript_json=[{"role": r, "content": c} for r, c in conversation.turns], extracted_json={}
    )
    turn = run_structured(
        "onboarding", onboarding.InterviewTurn, onboarding._build_messages(session, LOCALE, config)
    )
    clean = onboarding.validate_extracted(turn.extracted_delta(), config.extraction_schema)
    return {
        "extracted": clean,
        "done": turn.done,
        "proposal": turn.proposal.model_dump() if turn.proposal else None,
    }


def _get(tree: dict, path: str) -> Any:
    node: Any = tree
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


@dataclass
class Settles(Evaluator):
    """The answer settled these fields with these values (lists: contains, case-insensitive)."""

    expected: dict[str, Any]

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        results = {}
        for path, want in self.expected.items():
            got = _get(ctx.output["extracted"], path)
            if isinstance(want, list):
                have = {str(x).casefold() for x in (got or [])}
                ok = all(any(w.casefold() in h for h in have) for w in want)
            else:
                ok = got == want
            results[f"settles:{path}"] = ok
        return results


@dataclass
class IncomeSources(Evaluator):
    """`income.sources` holds exactly these sources (matched on the given fields);
    a bonus that depends on targets must never appear as a source."""

    expected: list[dict[str, Any]]

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        sources = _get(ctx.output["extracted"], "income.sources") or []
        results = {"income:source_count": len(sources) == len(self.expected)}
        for i, want in enumerate(self.expected):
            results[f"income:source_{i}"] = any(
                all(s.get(k) == v for k, v in want.items()) for s in sources
            )
        return results


@dataclass
class DoesNotSettle(Evaluator):
    paths: list[str]

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        return {f"absent:{p}": _get(ctx.output["extracted"], p) is None for p in self.paths}


@dataclass
class ProposalShape(Evaluator):
    """Credit cards become credit accounts; loans become categories, not accounts."""

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        proposal = ctx.output["proposal"]
        if not proposal:
            return {"proposal_present": False}
        accounts = {a["name"].casefold(): a["type"] for a in proposal["accounts"]}
        categories = " ".join(
            c["name"].casefold() for g in proposal["category_groups"] for c in g["categories"]
        )
        return {
            "proposal_present": True,
            "card_is_credit_account": any(t == "credit" and "visa" in n for n, t in accounts.items()),
            "loan_not_an_account": not any("préstamo" in n or "loan" in n for n in accounts),
            "has_car_categories": "gasolina" in categories or "combustible" in categories,
        }


FULL_INTERVIEW = Conversation(
    turns=[
        ("assistant", "¿Gestionas el dinero tú solo o en pareja?"),
        ("user", "Solo yo"),
        ("assistant", "¿De dónde vienen tus ingresos y cuánto entra al mes?"),
        ("user", "Nómina de 2.300 € que cobro el día 28"),
        ("assistant", "¿Qué bancos y tarjetas de crédito usas?"),
        ("user", "Una cuenta en BBVA y la Visa del BBVA"),
        ("assistant", "¿Vives de alquiler, con hipoteca o en casa propia?"),
        ("user", "Alquiler, 850 € al mes. Pago luz, agua e internet"),
        ("assistant", "¿Tienes coche?"),
        ("user", "Sí, uno"),
        ("assistant", "¿Alguna suscripción o deuda?"),
        ("user", "Netflix y Spotify. Debo el préstamo del coche, 210 € al mes"),
        ("assistant", "¿Algo más que quieras priorizar?"),
        ("user", "No, eso es todo. Prepárame el presupuesto."),
    ]
)


def dataset() -> Dataset:
    judge = route_config("judge")
    return Dataset(
        name="onboarding",
        cases=[
            Case(
                name="joint_household",
                inputs=_ask("¿Gestionas el dinero tú solo o en pareja?", "Lo llevamos entre mi pareja y yo"),
                evaluators=[Settles({"household.management_style": "joint"})],
            ),
            Case(
                name="income_salary",
                inputs=_ask(
                    "¿De dónde vienen tus ingresos y cuánto entra al mes?",
                    "Cobro una nómina de unos 2.350 € el día 27",
                ),
                evaluators=[IncomeSources([{"amount_cents": 235000, "day": 27}])],
            ),
            Case(
                name="income_two_sources_extra_pays_and_bonus",
                inputs=_ask(
                    "¿De dónde vienen tus ingresos y cuánto entra al mes?",
                    "Cobro 2.000 netos el 27 en 14 pagas de Acme, mi pareja 1.500 el día 1, "
                    "y un bonus si la empresa cumple objetivos",
                ),
                evaluators=[
                    IncomeSources([
                        {"amount_cents": 200000, "day": 27, "payments_per_year": 14},
                        {"amount_cents": 150000, "day": 1},
                    ])
                ],
            ),
            Case(
                name="banks_and_cards",
                inputs=_ask(
                    "¿Qué bancos y tarjetas de crédito usas?",
                    "BBVA y una cuenta de Sabadell, y la Visa del BBVA",
                ),
                evaluators=[Settles({"accounts.banks": ["bbva", "sabadell"], "accounts.credit_cards": ["visa"]})],
            ),
            Case(
                name="balance_skipped",
                inputs=_ask(
                    "¿Cuánto tienes ahora en tu cuenta principal? Puedes saltarte esta pregunta.",
                    "Prefiero no decirlo",
                ),
                evaluators=[DoesNotSettle(["accounts.main_balance_cents"])],
            ),
            Case(
                name="renting_utilities",
                inputs=_ask(
                    "¿Vives de alquiler, con hipoteca o en casa propia? ¿Qué suministros pagas?",
                    "De alquiler. Pago la luz y el agua, no tengo gas",
                ),
                evaluators=[Settles({"housing.status": "rent", "housing.utilities": ["electric", "water"]})],
            ),
            Case(
                name="final_proposal",
                inputs=FULL_INTERVIEW,
                evaluators=[
                    ProposalShape(),
                    LLMJudge(
                        rubric=(
                            "The output is a budget setup proposal for the user in the conversation "
                            "(Spanish, single, 2.300 € salary, rents for 850 €, utilities, one car, "
                            "Netflix and Spotify, a car loan and a Visa card). Pass if the categories "
                            "cover rent, utilities, groceries, the car's true expenses (fuel, insurance, "
                            "maintenance), the subscriptions and the loan payment, with names in Spanish "
                            "and no duplicates. Think step by step before deciding."
                        ),
                        model=_model("judge", judge),
                        include_input=True,
                    ),
                ],
            ),
        ],
    )


def task(conversation: Conversation) -> dict[str, Any]:
    return interview_turn(conversation)
