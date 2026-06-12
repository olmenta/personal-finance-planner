"""Suggestion service tests — LiteLLM call fully mocked, no live requests."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ingestion import NormalizedTransaction
from app.services import category_suggestions
from app.services.category_suggestions import (
    EMPTY,
    HistoryExample,
    RowSuggestion,
    Suggestion,
    SuggestionResponse,
    suggest,
)


def _category(category_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=category_id, name=name, group=SimpleNamespace(name="Esenciales"))


def _row(description: str, hint: str | None = None) -> NormalizedTransaction:
    return NormalizedTransaction(
        date=date(2026, 6, 1),
        amount_cents=-1000,
        currency="EUR",
        description=description,
        category_hint=hint,
    )


def _settings_with_key():
    return SimpleNamespace(anthropic_api_key="sk-test", anthropic_model="claude-opus-4-8")


class TestSuggest:
    def test_suggestion_mapped(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(
            return_value=SuggestionResponse(
                suggestions=[RowSuggestion(row=0, category_id="cat-1", payee="Mercadona", confidence="high")]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            result = suggest(categories, [_row("MERCADONA VALENCIA")])
        assert result == {0: Suggestion("cat-1", "Mercadona", "high")}

    def test_hint_included_in_prompt(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(return_value=SuggestionResponse(suggestions=[]))
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            suggest(categories, [_row("Tienda", hint="comida")])
        prompt = call.call_args.args[0]
        assert "hint: comida" in prompt

    def test_hallucinated_id_becomes_null(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(
            return_value=SuggestionResponse(
                suggestions=[RowSuggestion(row=0, category_id="not-a-real-id")]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            result = suggest(categories, [_row("???")])
        assert result == {0: EMPTY}

    def test_exception_degrades_to_all_null(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(side_effect=RuntimeError("rate limited"))
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            result = suggest(categories, [_row("a"), _row("b")])
        assert result == {0: EMPTY, 1: EMPTY}

    def test_missing_key_skips_call(self):
        categories = [_category("cat-1", "Supermercado")]
        no_key = lambda: SimpleNamespace(anthropic_api_key=None, anthropic_model="m")
        with patch.object(category_suggestions, "get_settings", no_key):
            result = suggest(categories, [_row("a")])
        assert result == {0: EMPTY}


class TestHistoryAndConfidence:
    def test_history_examples_in_prompt(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(return_value=SuggestionResponse(suggestions=[]))
        history = [HistoryExample("GASOLINERA REPSOL", "Repsol", "Gasolina")]
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            suggest(categories, [_row("REPSOL AVENIDA")], history)
        prompt = call.call_args.args[0]
        assert "GASOLINERA REPSOL | Repsol | Gasolina" in prompt

    def test_missing_confidence_defaults_low(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(
            return_value=SuggestionResponse(
                suggestions=[RowSuggestion(row=0, category_id="cat-1")]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            result = suggest(categories, [_row("MERCADONA")])
        assert result[0].confidence == "low"
        assert result[0].payee is None

    def test_payee_trimmed_and_capped(self):
        categories = [_category("cat-1", "Supermercado")]
        call = MagicMock(
            return_value=SuggestionResponse(
                suggestions=[
                    RowSuggestion(row=0, category_id=None, payee="  " + "x" * 200)
                ]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_call_model", call),
        ):
            result = suggest(categories, [_row("???")])
        assert result[0].payee == "x" * 120
        assert result[0].category_id is None


class TestSampleHistory:
    def test_distinct_recent_with_payee(self, client, db, user, category_ids):
        client.post(
            "/transactions",
            json={
                "amount_cents": 100,
                "category_id": category_ids["Supermercado"],
                "payee": "Mercadona",
                "note": "MERCADONA VALENCIA",
                "date": "2026-06-09",
            },
        )
        # Same description again — must collapse to the newest occurrence.
        client.post(
            "/transactions",
            json={
                "amount_cents": 200,
                "category_id": category_ids["Supermercado"],
                "note": "MERCADONA VALENCIA",
                "date": "2026-06-10",
            },
        )
        client.post(
            "/transactions",
            json={
                "amount_cents": 300,
                "category_id": category_ids["Gasolina"],
                "note": "REPSOL A7",
                "date": "2026-06-08",
            },
        )
        examples = category_suggestions.sample_history(db, user.id)
        descriptions = [e.description for e in examples]
        assert descriptions == ["MERCADONA VALENCIA", "REPSOL A7"]
        assert examples[1].category_name == "Gasolina"
