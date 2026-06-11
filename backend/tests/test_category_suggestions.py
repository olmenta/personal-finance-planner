"""Suggestion service tests — Anthropic client fully mocked, no live calls."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ingestion import NormalizedTransaction
from app.services import category_suggestions
from app.services.category_suggestions import RowSuggestion, SuggestionResponse, suggest


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
        client = MagicMock()
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=SuggestionResponse(
                suggestions=[RowSuggestion(row=0, category_id="cat-1")]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_client", return_value=client),
        ):
            result = suggest(categories, [_row("MERCADONA VALENCIA")])
        assert result == {0: "cat-1"}

    def test_hint_included_in_prompt(self):
        categories = [_category("cat-1", "Supermercado")]
        client = MagicMock()
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=SuggestionResponse(suggestions=[])
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_client", return_value=client),
        ):
            suggest(categories, [_row("Tienda", hint="comida")])
        prompt = client.messages.parse.call_args.kwargs["messages"][0]["content"]
        assert "hint: comida" in prompt

    def test_hallucinated_id_becomes_null(self):
        categories = [_category("cat-1", "Supermercado")]
        client = MagicMock()
        client.messages.parse.return_value = SimpleNamespace(
            parsed_output=SuggestionResponse(
                suggestions=[RowSuggestion(row=0, category_id="not-a-real-id")]
            )
        )
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_client", return_value=client),
        ):
            result = suggest(categories, [_row("???")])
        assert result == {0: None}

    def test_exception_degrades_to_all_null(self):
        categories = [_category("cat-1", "Supermercado")]
        client = MagicMock()
        client.messages.parse.side_effect = RuntimeError("rate limited")
        with (
            patch.object(category_suggestions, "get_settings", _settings_with_key),
            patch.object(category_suggestions, "_client", return_value=client),
        ):
            result = suggest(categories, [_row("a"), _row("b")])
        assert result == {0: None, 1: None}

    def test_missing_key_skips_call(self):
        categories = [_category("cat-1", "Supermercado")]
        no_key = lambda: SimpleNamespace(anthropic_api_key=None, anthropic_model="m")
        with patch.object(category_suggestions, "get_settings", no_key):
            result = suggest(categories, [_row("a")])
        assert result == {0: None}
