"""AI category + payee suggestions for transactions (design D1).

Structured-output LLM calls (via LiteLLM — provider stays configuration,
never code): the user's category tree, a sample of their own categorization
history as worked examples, and the numbered rows go in; per row a category
id, a cleaned payee name, and a confidence level come out. Rows are sent in
chunks of CHUNK_ROWS so one failed or truncated call degrades only its own
chunk. Ids are validated against the user's real categories; any failure —
missing key, rate limit, timeout, truncated output — degrades the affected
rows to all-null so the caller always succeeds (fail-open). Income rows
(positive amounts) never get a category — income lands in "ready to
assign", not in budget envelopes.

Transaction descriptions are sent to the model provider (data-processor
posture, project-definition §6.2); no other PII leaves the system.
"""

import logging
from typing import Literal, NamedTuple

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ingestion import NormalizedTransaction
from ..models import Category, Payee, Transaction

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 100
CHUNK_ROWS = 200

Confidence = Literal["high", "medium", "low"]


class Suggestion(NamedTuple):
    category_id: str | None
    payee: str | None
    confidence: Confidence


class HistoryExample(NamedTuple):
    description: str
    payee_name: str | None
    category_name: str


EMPTY = Suggestion(None, None, "low")


class RowSuggestion(BaseModel):
    row: int
    category_id: str | None
    # Clean merchant/payer name extracted from the raw description
    # ("COMPRA TARJ. 4188 MERCADONA VALENCIA" -> "Mercadona"); null when unclear.
    payee: str | None = None
    confidence: Confidence | None = None  # missing degrades to "low"


class SuggestionResponse(BaseModel):
    suggestions: list[RowSuggestion]


def sample_history(db: Session, user_id: str) -> list[HistoryExample]:
    """Up to ~100 distinct recent (description, payee, category) examples.

    Newest first, distinct by description — recency beats frequency for
    drifting habits, distinctness keeps one merchant from filling the
    sample (design D1).
    """
    rows = db.execute(
        select(Transaction.description, Payee.name, Category.name)
        .join(Category, Category.id == Transaction.category_id)
        .outerjoin(Payee, Payee.id == Transaction.payee_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == "confirmed",
            Transaction.description.is_not(None),
        )
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(HISTORY_LIMIT * 5)
    ).all()

    examples: list[HistoryExample] = []
    seen: set[str] = set()
    for description, payee_name, category_name in rows:
        key = description.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        examples.append(HistoryExample(description, payee_name, category_name))
        if len(examples) >= HISTORY_LIMIT:
            break
    return examples


def _build_prompt(
    categories: list[Category],
    rows: list[NormalizedTransaction],
    history: list[HistoryExample],
) -> str:
    lines = [
        "You categorize Spanish bank transactions for a personal budgeting app.",
        "For each transaction return:",
        "- category_id: the best-fitting category id from the user's tree below,",
        "  or null when no category clearly fits. Positive amounts are income:",
        "  always return null category for them — income is not budgeted into",
        "  categories in this app. Still extract the payer name.",
        "- payee: the clean merchant or payer name extracted from the raw bank",
        '  description (e.g. "COMPRA TARJ. 4188 MERCADONA VALENCIA" -> "Mercadona"),',
        "  or null when no clear payee can be read. Never return card numbers,",
        "  branch cities, or transaction noise as part of the name.",
        '- confidence: "high", "medium" or "low" for the suggestion as a whole.',
        "",
        "Categories (id | group | name):",
    ]
    for category in categories:
        lines.append(f"{category.id} | {category.group.name} | {category.name}")
    if history:
        lines += [
            "",
            "How this user has categorized before (description | payee | category).",
            "Follow these patterns when the same merchant appears:",
        ]
        for example in history:
            lines.append(
                f"{example.description} | {example.payee_name or '-'} | {example.category_name}"
            )
    lines += [
        "",
        "Transactions (row | date | amount in cents, negative = expense | description).",
        "Positive rows are inflows: suggest a category ONLY when the description",
        "matches a merchant in the user's history above (a refund of that spending);",
        "regular income (salary, benefits) must get category_id null.",
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


def _call_model(prompt: str) -> SuggestionResponse | None:
    """One LiteLLM structured-output call. Raises on transport errors;
    returns None when the model produced no parseable content."""
    import litellm

    settings = get_settings()
    model = settings.anthropic_model
    if "/" not in model:  # bare names default to the Anthropic provider
        model = f"anthropic/{model}"
    response = litellm.completion(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        response_format=SuggestionResponse,
        api_key=settings.anthropic_api_key,
    )
    content = response.choices[0].message.content
    if not content:
        return None
    return SuggestionResponse.model_validate_json(content)


def suggest(
    categories: list[Category],
    rows: list[NormalizedTransaction],
    history: list[HistoryExample] | None = None,
) -> dict[int, Suggestion]:
    """Map row index -> Suggestion(category_id, payee, confidence). Never raises.

    Rows go to the model in chunks of CHUNK_ROWS; a failed or unparseable
    call degrades only its own chunk to EMPTY, not the whole batch.
    """
    empty: dict[int, Suggestion] = {i: EMPTY for i in range(len(rows))}
    if not rows or not categories:
        return empty
    if not get_settings().anthropic_api_key:
        logger.warning("category suggestions skipped: ANTHROPIC_API_KEY not set")
        return empty

    result = dict(empty)
    for start in range(0, len(rows), CHUNK_ROWS):
        chunk = rows[start : start + CHUNK_ROWS]
        for offset, suggestion in _suggest_chunk(
            categories, chunk, history or [], start
        ).items():
            result[start + offset] = suggestion
    return result


def _suggest_chunk(
    categories: list[Category],
    chunk: list[NormalizedTransaction],
    history: list[HistoryExample],
    start: int,
) -> dict[int, Suggestion]:
    """One model call for one chunk; {} on any failure (fail-open)."""
    try:
        parsed = _call_model(_build_prompt(categories, chunk, history))
    except Exception:
        logger.warning(
            "category suggestions degraded: LLM call failed (rows %d-%d)",
            start,
            start + len(chunk) - 1,
            exc_info=True,
        )
        return {}
    if parsed is None:
        logger.warning(
            "category suggestions degraded: unparseable model output (rows %d-%d)",
            start,
            start + len(chunk) - 1,
        )
        return {}

    valid_ids = {category.id for category in categories}
    result: dict[int, Suggestion] = {}
    for item in parsed.suggestions:
        if not (0 <= item.row < len(chunk)):
            continue
        payee = (item.payee or "").strip()[:120] or None
        # Hallucinated ids become null — only real categories pass.
        category_id = item.category_id if item.category_id in valid_ids else None
        # Income is never categorized — it lands in "ready to assign".
        if chunk[item.row].amount_cents > 0:
            category_id = None
        result[item.row] = Suggestion(
            category_id=category_id,
            payee=payee,
            confidence=item.confidence or "low",
        )
    return result
