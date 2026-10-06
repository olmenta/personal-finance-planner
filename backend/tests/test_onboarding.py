"""Onboarding interview tests — model call fully mocked, no live requests."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    Category,
    CategoryGroup,
    IncomeSchedule,
    OnboardingSession,
    Payee,
    Transaction,
    UserPreferences,
)
from app.services import onboarding
from app.services.category_setup import DEFAULT_CATEGORY_TREE
from app.services.onboarding import (
    InterviewTurn,
    OnboardingUnavailable,
    ProposedAccount,
    ProposedCategory,
    ProposedGroup,
    ModelProposal,
    load_prompt_config,
    merge_extracted,
    proposed_income,
    validate_extracted,
)
from app.services.preferences import PreferencesStore


def _settings_with_key():
    return SimpleNamespace(anthropic_api_key="sk-test", anthropic_model="claude-opus-4-8")


def _opening_turn() -> InterviewTurn:
    return InterviewTurn(
        message="Managing money alone, or jointly?",
        input_kind="chips",
        options=["Alone", "Jointly"],
    )


def _proposal() -> ModelProposal:
    return ModelProposal(
        accounts=[
            ProposedAccount(name="BBVA", type="bank"),
            ProposedAccount(name="Visa BBVA", type="credit"),
        ],
        category_groups=[
            ProposedGroup(
                name="Vivienda",
                categories=[ProposedCategory(name="Hipoteca", icon="home")],
            ),
            ProposedGroup(
                name="Fondos previstos",
                categories=[ProposedCategory(name="IBI", icon="receipt")],
            ),
        ],
        payers=["Nómina empresa"],
        payees=["Netflix", "Gimnasio"],
    )


FOURTEEN_PAGAS = {
    "income": {
        "sources": [
            {"name": "Nómina", "payer": "Acme", "amount_cents": 200000, "day": 27,
             "payments_per_year": 14}
        ]
    }
}


def _done_turn(proposal: ModelProposal | None = None, extracted: dict | None = None) -> InterviewTurn:
    return InterviewTurn(
        message="All set!",
        done=True,
        proposal=proposal,
        extracted=json.dumps(extracted) if extracted else None,
    )


def _start(client, turn: InterviewTurn | None = None):
    call = MagicMock(return_value=turn or _opening_turn())
    with patch.object(onboarding, "_call_model", call):
        return client.post("/onboarding/start")


class TestExtractionValidation:
    SCHEMA = load_prompt_config().extraction_schema

    def test_unknown_keys_dropped(self):
        clean = validate_extracted(
            {"household": {"children": True, "favorite_color": "red"}, "ssn": "x"},
            self.SCHEMA,
        )
        assert clean == {"household": {"children": True}}

    def test_ill_typed_values_dropped(self):
        clean = validate_extracted(
            {"income": {"sources": [{"name": "Nómina", "day": "27", "amount_cents": 240000}]}},
            self.SCHEMA,
        )
        assert clean == {"income": {"sources": [{"name": "Nómina", "amount_cents": 240000}]}}

    def test_object_list_items_validated(self):
        clean = validate_extracted(
            {"income": {"sources": [
                {"name": "Nómina", "payments_per_year": 13, "bonus": True},
                {"bonus": True},  # nothing valid left: the item is dropped
                "Nómina empresa",  # not an object
            ]}},
            self.SCHEMA,
        )
        assert clean == {"income": {"sources": [{"name": "Nómina"}]}}
        assert validate_extracted({"income": {"sources": "Nómina"}}, self.SCHEMA) == {}

    def test_legacy_income_field_dropped(self):
        assert validate_extracted({"income": {"expected_monthly_cents": 240000}}, self.SCHEMA) == {}


    def test_enum_checked(self):
        assert validate_extracted({"housing": {"status": "castle"}}, self.SCHEMA) == {}
        assert validate_extracted({"housing": {"status": "rent"}}, self.SCHEMA) == {
            "housing": {"status": "rent"}
        }

    def test_merge_is_deep(self):
        base = {"income": {"sources": ["a"]}, "housing": {"status": "rent"}}
        delta = {"income": {"income_day": 27}}
        assert merge_extracted(base, delta) == {
            "income": {"sources": ["a"], "income_day": 27},
            "housing": {"status": "rent"},
        }



class TestProposedIncome:
    def test_two_sources_with_extra_pays(self):
        extracted = {"income": {"sources": [
            {"name": "Nómina", "payer": "Acme", "amount_cents": 200000, "day": 27,
             "payments_per_year": 14},
            {"name": "Nómina Ana", "amount_cents": 150000, "day": 1, "payments_per_year": 12},
        ]}}
        assert [i.model_dump() for i in proposed_income(extracted)] == [
            {"name": "Nómina", "payer": "Acme", "amount_cents": 200000, "pattern": "monthly",
             "months": None, "day": 27},
            {"name": "Paga extra", "payer": "Acme", "amount_cents": 200000,
             "pattern": "some_months", "months": [6, 12], "day": 27},
            {"name": "Nómina Ana", "payer": None, "amount_cents": 150000, "pattern": "monthly",
             "months": None, "day": 1},
        ]

    def test_sources_without_amount_skipped(self):
        assert proposed_income({"income": {"sources": [{"name": "Freelance"}]}}) == []

    def test_legacy_answers_map_to_one_monthly_schedule(self):
        legacy = {"income": {"sources": ["Nómina empresa"], "expected_monthly_cents": 240000,
                             "income_day": 27}}
        [income] = proposed_income(legacy)
        assert (income.name, income.amount_cents, income.pattern, income.day) == (
            "Nómina empresa", 240000, "monthly", 27)

    def test_no_income_known(self):
        assert proposed_income({}) == []

class TestSessionLifecycle:
    def test_start_creates_session_with_opening_turn(self, client, db, user):
        response = _start(client)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["prompt_version"] == "onboarding_v3"
        assert body["transcript"][0]["role"] == "assistant"
        assert body["transcript"][0]["input_kind"] == "chips"
        assert body["transcript"][0]["options"] == ["Alone", "Jointly"]

    def test_start_idempotent_on_active_session(self, client, db, user):
        first = _start(client).json()
        second = _start(client).json()
        assert second["id"] == first["id"]
        sessions = db.scalars(
            select(OnboardingSession).where(OnboardingSession.user_id == user.id)
        ).all()
        assert len(sessions) == 1

    def test_session_404_without_start(self, client):
        response = client.get("/onboarding/session")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_active_session"

    def test_resume_returns_transcript(self, client, db, user):
        _start(client)
        turn = InterviewTurn(message="Rent or own?", input_kind="chips", options=["Rent", "Own"])
        with patch.object(onboarding, "_call_model", MagicMock(return_value=turn)):
            client.post("/onboarding/messages", json={"message": "Jointly"})
        body = client.get("/onboarding/session").json()
        roles = [entry["role"] for entry in body["transcript"]]
        assert roles == ["assistant", "user", "assistant"]
        assert body["transcript"][1]["content"] == "Jointly"


class TestTurns:
    def test_extracted_delta_merged_and_unknown_dropped(self, client, db, user):
        _start(client)
        turn = InterviewTurn(
            message="Got it.",
            extracted=json.dumps(
                {"household": {"management_style": "joint", "spouse_name": "Ana"}}
            ),
        )
        with patch.object(onboarding, "_call_model", MagicMock(return_value=turn)):
            client.post("/onboarding/messages", json={"message": "Jointly"})
        session = onboarding.get_active_session(db, user.id)
        assert session.extracted_json == {"household": {"management_style": "joint"}}

    def test_done_stores_proposal(self, client, db, user):
        _start(client)
        with patch.object(
            onboarding,
            "_call_model",
            MagicMock(return_value=_done_turn(_proposal(), extracted=FOURTEEN_PAGAS)),
        ):
            response = client.post("/onboarding/messages", json={"message": "No debts"})
        body = response.json()
        assert body["transcript"][-1]["done"] is True
        assert body["proposal"]["payees"] == ["Netflix", "Gimnasio"]
        assert body["proposal"]["accounts"] == [
            {"name": "BBVA", "type": "bank"},
            {"name": "Visa BBVA", "type": "credit"},
        ]
        # Fourteen pagas proposed as two schedules, built in code from the extraction.
        assert [(i["name"], i["pattern"], i["months"], i["payer"]) for i in body["proposal"]["income"]] == [
            ("Nómina", "monthly", None, "Acme"),
            ("Paga extra", "some_months", [6, 12], "Acme"),
        ]

    def test_done_without_proposal_reasked_once(self, client, db, user):
        _start(client)
        call = MagicMock(side_effect=[_done_turn(None), _done_turn(_proposal())])
        with patch.object(onboarding, "_call_model", call):
            response = client.post("/onboarding/messages", json={"message": "No debts"})
        assert response.status_code == 200
        assert response.json()["proposal"] is not None
        assert call.call_count == 2

    def test_done_without_proposal_twice_is_503(self, client, db, user):
        _start(client)
        call = MagicMock(side_effect=[_done_turn(None), _done_turn(None)])
        with patch.object(onboarding, "_call_model", call):
            response = client.post("/onboarding/messages", json={"message": "No debts"})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "onboarding_unavailable"

    def test_failed_call_is_503(self, client, db, user):
        _start(client)
        call = MagicMock(side_effect=OnboardingUnavailable("boom"))
        with patch.object(onboarding, "_call_model", call):
            response = client.post("/onboarding/messages", json={"message": "hi"})
        assert response.status_code == 503

    def test_start_without_key_is_503(self, client, db, user):
        no_key = SimpleNamespace(anthropic_api_key=None, anthropic_model="claude-opus-4-8")
        with patch.object(onboarding, "get_settings", lambda: no_key):
            response = client.post("/onboarding/start")
        assert response.status_code == 503
        assert onboarding.get_active_session(db, user.id) is None


class TestFinalize:
    def _finish(self, client) -> str:
        _start(client)
        with patch.object(
            onboarding, "_call_model", MagicMock(return_value=_done_turn(_proposal()))
        ):
            body = client.post("/onboarding/messages", json={"message": "done"}).json()
        return body["id"]

    def test_reviewed_payload_created_exactly(self, client, db, user):
        session_id = self._finish(client)
        payload = {
            "category_groups": [
                {
                    "name": "Fondos previstos",
                    "categories": [
                        {"name": "IBI", "icon": "receipt"},
                        {"name": "Club de pádel", "icon": "circle"},  # user-added
                    ],
                }
                # "Vivienda"/"Hipoteca" unchecked by the user — must not be created
            ],
            "payers": ["Nómina empresa"],
            "payees": ["Netflix"],
            "income": [{"name": "Nómina", "payer": "Nómina empresa", "amount_cents": 240000,
                        "pattern": "monthly", "day": 27}],
        }
        response = client.post(f"/onboarding/{session_id}/finalize", json=payload)
        assert response.status_code == 200
        names = set(db.scalars(select(Category.name).where(Category.user_id == user.id)))
        assert {"IBI", "Club de pádel"} <= names
        assert "Hipoteca" not in names

    def test_existing_group_reused_case_insensitively(self, client, db, user):
        session_id = self._finish(client)
        payload = {
            "category_groups": [
                {"name": "vivienda", "categories": [{"name": "Hipoteca", "icon": "home"}]}
            ],
            "payers": [],
            "payees": [],
        }
        client.post(f"/onboarding/{session_id}/finalize", json=payload)
        groups = db.scalars(
            select(CategoryGroup).where(CategoryGroup.user_id == user.id)
        ).all()
        vivienda = [g for g in groups if g.name.lower() == "vivienda"]
        assert len(vivienda) == 1  # seeded group reused, no duplicate

    def test_payees_seeded(self, client, db, user):
        session_id = self._finish(client)
        payload = {
            "category_groups": [],
            "payers": ["Nómina empresa"],
            "payees": ["Netflix", "netflix "],  # dupe collapses case-insensitively
        }
        response = client.post(f"/onboarding/{session_id}/finalize", json=payload)
        assert response.json()["payees_created"] == 2
        names = set(db.scalars(select(Payee.name).where(Payee.user_id == user.id)))
        assert names == {"Nómina empresa", "Netflix"}

    def test_income_schedules_created_and_preferences_written(self, client, db, user):
        session_id = self._finish(client)
        payload = {
            "category_groups": [],
            "payers": [],
            "payees": [],
            # Reviewed: salary edited to 2.050 €, extra pay kept.
            "income": [
                {"name": "Nómina", "payer": "Acme", "amount_cents": 205000, "pattern": "monthly",
                 "day": 27},
                {"name": "Paga extra", "payer": "Acme", "amount_cents": 200000,
                 "pattern": "some_months", "months": [6, 12], "day": 27},
            ],
        }
        assert client.post(f"/onboarding/{session_id}/finalize", json=payload).status_code == 200
        schedules = {s["name"]: s for s in client.get("/income-schedules").json()}
        assert schedules["Nómina"]["amount_cents"] == 205000
        assert schedules["Paga extra"]["months"] == [6, 12]
        assert schedules["Nómina"]["payee_id"] == schedules["Paga extra"]["payee_id"] is not None
        assert client.get("/plan/upcoming?from=2026-10").json()["income_known"] is True
        # No budget income is written: monthly income stays derived from transactions.
        assert client.get("/budget/2026-10").json()["income_cents"] == 0
        record = PreferencesStore(db).get(user.id)
        assert record is not None
        assert record.prompt_version == "onboarding_v3"
        assert "expected_monthly_cents" not in record.preferences.get("income", {})
        session = db.get(OnboardingSession, session_id)
        assert session.status == "completed"
        assert session.completed_at is not None

    def test_accounts_created_with_card_payment_category(self, client, db, user):
        session_id = self._finish(client)
        payload = {
            "accounts": [{"name": "BBVA", "type": "bank"}, {"name": "Visa BBVA", "type": "credit"}],
            "category_groups": [],
        }
        assert client.post(f"/onboarding/{session_id}/finalize", json=payload).status_code == 200
        accounts = {a["name"]: a for a in client.get("/accounts").json()}
        assert accounts["BBVA"]["type"] == "bank"
        assert accounts["Visa BBVA"]["type"] == "credit"
        assert accounts["Visa BBVA"]["balance_cents"] == 0
        payment = db.scalar(
            select(Category).where(Category.payment_account_id == accounts["Visa BBVA"]["id"])
        )
        assert payment is not None and payment.name == "Pago Visa BBVA"
        assert db.get(CategoryGroup, payment.group_id).system is True
        # No balance given in the interview: nothing written.
        assert db.scalar(
            select(Transaction).where(Transaction.account_id == accounts["BBVA"]["id"])
        ) is None

    def test_existing_account_reused_and_opening_balance_written(self, client, db, user):
        session_id = self._finish(client)
        session = db.get(OnboardingSession, session_id)
        session.extracted_json = {"accounts": {"main_balance_cents": 180000}}
        db.flush()
        payload = {
            "accounts": [{"name": "efectivo", "type": "bank"}, {"name": "Cuenta nómina", "type": "bank"}],
            "category_groups": [],
        }
        assert client.post(f"/onboarding/{session_id}/finalize", json=payload).status_code == 200
        names = list(db.scalars(select(Account.name).where(Account.user_id == user.id)))
        assert sorted(names) == ["Cuenta nómina", "Efectivo"]  # seeded one reused
        nomina = db.scalar(select(Account).where(Account.name == "Cuenta nómina"))
        opening = db.scalar(select(Transaction).where(Transaction.account_id == nomina.id))
        assert opening.amount_cents == 180000
        assert opening.source == "opening_balance"
        assert opening.category_id is None and opening.status == "confirmed"

    def test_finalize_twice_is_409(self, client, db, user):
        session_id = self._finish(client)
        empty = {"category_groups": [], "payers": [], "payees": []}
        assert client.post(f"/onboarding/{session_id}/finalize", json=empty).status_code == 200
        response = client.post(f"/onboarding/{session_id}/finalize", json=empty)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "session_not_active"

    def test_finalize_unknown_session_404(self, client):
        empty = {"category_groups": [], "payers": [], "payees": []}
        response = client.post("/onboarding/nope/finalize", json=empty)
        assert response.status_code == 404

    def test_failure_persists_nothing(self, db, user, client):
        session_id = self._finish(client)
        session = db.get(OnboardingSession, session_id)
        from app.schemas import OnboardingFinalizeRequest, OnboardingGroupIn, OnboardingCategoryIn

        payload = OnboardingFinalizeRequest(
            category_groups=[
                OnboardingGroupIn(
                    name="Nuevo grupo", categories=[OnboardingCategoryIn(name="Nueva")]
                )
            ],
            payees=["Netflix"],
            income=[{"name": "Nómina", "amount_cents": 200000, "pattern": "monthly"}],
        )
        with patch.object(PreferencesStore, "put", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                onboarding.finalize(db, session, payload)
        db.rollback()
        names = set(db.scalars(select(Category.name).where(Category.user_id == user.id)))
        assert "Nueva" not in names
        assert db.scalar(select(Payee).where(Payee.user_id == user.id)) is None
        assert db.scalar(select(IncomeSchedule).where(IncomeSchedule.user_id == user.id)) is None


class TestStatus:
    def test_status_reflects_lifecycle(self, client, db, user):
        assert client.get("/onboarding/status").json() == {
            "has_completed": False,
            "has_active": False,
        }
        session_id = _start(client).json()["id"]
        assert client.get("/onboarding/status").json() == {
            "has_completed": False,
            "has_active": True,
        }
        empty = {"category_groups": [], "payers": [], "payees": []}
        client.post(f"/onboarding/{session_id}/finalize", json=empty)
        assert client.get("/onboarding/status").json() == {
            "has_completed": True,
            "has_active": False,
        }


class TestTemplateFallback:
    def test_template_creates_default_tree(self, client, db, user):
        # The dev seed already created the default tree, so nothing new here —
        # the endpoint reports zero creations and stays idempotent.
        response = client.post("/onboarding/template")
        assert response.status_code == 200
        assert response.json() == {"categories_created": 0, "payees_created": 0}

    def test_template_abandons_active_session_and_fills_gaps(self, client, db, user):
        session_id = _start(client).json()["id"]
        # Remove one seeded category to prove the template fills gaps.
        category = db.scalar(
            select(Category).where(Category.user_id == user.id, Category.name == "Supermercado")
        )
        db.delete(category)
        db.flush()
        response = client.post("/onboarding/template")
        assert response.json()["categories_created"] == 1
        assert db.get(OnboardingSession, session_id).status == "abandoned"
        default_names = {name for _, cats in DEFAULT_CATEGORY_TREE for name, _ in cats}
        names = set(db.scalars(select(Category.name).where(Category.user_id == user.id)))
        assert default_names <= names

    def test_no_preferences_document_from_template(self, client, db, user):
        client.post("/onboarding/template")
        assert PreferencesStore(db).get(user.id) is None
