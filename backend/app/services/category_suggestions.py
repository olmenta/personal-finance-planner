"""AI category suggestions for ingested transactions (design D5).

One structured-output Anthropic call per import batch: the user's category
tree plus the numbered rows go in, a row-index → category-id mapping comes
out. Ids are validated against the user's real categories; any failure —
missing key, rate limit, timeout, truncated output — degrades to all-null so
the import always succeeds.

Transaction descriptions are sent to Anthropic (data-processor posture,
project-definition §6.2); no other PII leaves the system.
"""

import logging

from pydantic import BaseModel

from ..config import get_settings
from ..ingestion import NormalizedTransaction
from ..models import Category

logger = logging.getLogger(__name__)


class RowSuggestion(BaseModel):
    row: int
    category_id: str | None


class SuggestionResponse(BaseModel):
    suggestions: list[RowSuggestion]


def _build_prompt(categories: list[Category], rows: list[NormalizedTransaction]) -> str:
    lines = [
        "You categorize Spanish bank transactions for a personal budgeting app.",
        "Assign each transaction the best-fitting category id from the user's",
        "category tree below, or null when no category clearly fits.",
        "",
        "Categories (id | group | name):",
    ]
    for category in categories:
        lines.append(f"{category.id} | {category.group.name} | {category.name}")
    lines += [
        "",
        "Transactions (row | date | amount in cents, negative = expense | description).",
        "Some rows carry a user-written category hint — it may not match any",
        "category name exactly; map it onto the closest category in the tree.",
    ]
    for index, row in enumerate(rows):
        line = f"{index} | {row.date.isoformat()} | {row.amount_cents} | {row.description}"
        if row.category_hint:
            line += f" | hint: {row.category_hint}"
        lines.append(line)
    lines += [
        "",
        "Return one suggestion per row, in row order.",
    ]
    return "\n".join(lines)


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def suggest(
    categories: list[Category], rows: list[NormalizedTransaction]
) -> dict[int, str | None]:
    """Map row index -> suggested category id (or None). Never raises."""
    empty: dict[int, str | None] = {i: None for i in range(len(rows))}
    if not rows or not categories:
        return empty
    if not get_settings().anthropic_api_key:
        logger.warning("category suggestions skipped: ANTHROPIC_API_KEY not set")
        return empty

    try:
        response = _client().messages.parse(
            model=get_settings().anthropic_model,
            max_tokens=16000,
            messages=[{"role": "user", "content": _build_prompt(categories, rows)}],
            output_format=SuggestionResponse,
        )
        parsed = response.parsed_output
        if parsed is None:
            logger.warning("category suggestions degraded: unparseable model output")
            return empty
    except Exception:
        logger.warning("category suggestions degraded: Anthropic call failed", exc_info=True)
        return empty

    valid_ids = {category.id for category in categories}
    result = dict(empty)
    for item in parsed.suggestions:
        if 0 <= item.row < len(rows):
            # Hallucinated ids become null — only real categories pass through.
            result[item.row] = item.category_id if item.category_id in valid_ids else None
    return result
