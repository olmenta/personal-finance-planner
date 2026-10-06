"""AI onboarding interview engine (spec: ai-onboarding, design D1–D5).

The interview script lives in a versioned prompt config
(app/prompts/onboarding_v3.md): YAML front matter declares the prompt
version and the extraction-field schema; the markdown body is the system
prompt. Each turn is one LiteLLM structured-output call (provider stays
configuration, never code). Extraction deltas are validated against the
declared schema — unknown keys are dropped and logged, never persisted.

Unlike import suggestions, the interview fails closed: a missing key or a
failed call (after one retry) raises OnboardingUnavailable, which the router
turns into 503 so the webapp can offer the starter-template fallback.

Transcript content is never logged (spec: transcript privacy).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, NamedTuple

import yaml
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..clock import today_madrid
from ..config import get_settings
from ..models import IncomeSchedule, OnboardingSession, Payee
from ..schemas import OnboardingFinalizeRequest
from ..llm import UsageContext, run_structured
from .accounts import create_account, find_by_name, write_opening_balance
from .category_setup import ensure_category, ensure_group
from .income import apply_schedule
from .payees import resolve_payee
from .preferences import PreferencesStore

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ACTIVE_PROMPT_FILE = "onboarding_v3.md"

LOCALE_NAMES = {"es": "Spanish", "en": "English"}

InputKind = Literal["chips", "checkboxes", "text", "money"]


class OnboardingUnavailable(Exception):
    """LLM key missing or the model call failed after retry — fail closed."""


class PromptConfig(NamedTuple):
    version: str
    extraction_schema: dict
    body: str


class ProposedCategory(BaseModel):
    name: str
    icon: str = "circle"


class ProposedGroup(BaseModel):
    name: str
    categories: list[ProposedCategory]


class ProposedIncome(BaseModel):
    """One income schedule for the review screen (spec: ai-onboarding)."""

    name: str
    payer: str | None = None
    amount_cents: int
    pattern: Literal["monthly", "some_months"] = "monthly"
    months: list[int] | None = None
    day: int | None = None


class ProposedAccount(BaseModel):
    name: str
    # Credit cards are accounts (with their payment category); loans stay
    # debt-paydown categories — tracking accounts are out of v1 scope.
    type: Literal["bank", "credit"] = "bank"


class ModelProposal(BaseModel):
    """What the model proposes. Income is not part of it: income schedules
    are derived from the extracted sources in code (design D7)."""

    accounts: list[ProposedAccount] = []
    category_groups: list[ProposedGroup]
    payers: list[str] = []
    payees: list[str] = []


class SetupProposal(ModelProposal):
    income: list[ProposedIncome] = []


class InterviewTurn(BaseModel):
    message: str
    input_kind: InputKind = "text"
    options: list[str] = []
    # JSON-encoded object string, not a dict: Anthropic structured output
    # rejects open objects (additionalProperties), and the delta's fields are
    # prompt-config-dynamic by design. Decoded via extracted_delta().
    extracted: str | None = None
    done: bool = False
    proposal: ModelProposal | None = None

    def extracted_delta(self) -> dict:
        if not self.extracted:
            return {}
        try:
            parsed = json.loads(self.extracted)
        except ValueError:
            logger.warning("onboarding turn carried unparseable extracted payload")
            return {}
        return parsed if isinstance(parsed, dict) else {}


@lru_cache
def load_prompt_config(filename: str = ACTIVE_PROMPT_FILE) -> PromptConfig:
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    meta = yaml.safe_load(front_matter)
    return PromptConfig(
        version=meta["version"],
        extraction_schema=meta["extraction_schema"],
        body=body.strip(),
    )


# ---------------------------------------------------------------------------
# Extraction validation — only schema-declared keys with matching types pass.

_INVALID = object()

_LEAF_CHECKS = {
    "bool": lambda v: isinstance(v, bool),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "string_list": lambda v: isinstance(v, list)
    and all(isinstance(item, str) for item in v),
}


def _validate_leaf(value: object, rule: object) -> object:
    if isinstance(rule, list):  # enum of allowed strings
        return value if value in rule else _INVALID
    check = _LEAF_CHECKS.get(rule)  # type: ignore[arg-type]
    return value if check is not None and check(value) else _INVALID


def _validate_object_list(key: str, value: object, rule: dict, path: str) -> object:
    """A list of objects (schema `[ {…} ]`): each item validated, empty ones dropped."""
    if not isinstance(value, list):
        logger.warning("onboarding extraction dropped non-list key: %s%s", path, key)
        return _INVALID
    items = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            clean = validate_extracted(item, rule, f"{path}{key}[{index}].")
            if clean:
                items.append(clean)
    return items if items else _INVALID


def _validate_field(key: str, value: object, rule: object, path: str) -> object:
    """One field against its schema rule; _INVALID drops it (logged by key
    name only — never values, privacy)."""
    if rule is None:
        logger.warning("onboarding extraction dropped unknown key: %s%s", path, key)
        return _INVALID
    if isinstance(rule, dict):
        if not isinstance(value, dict):
            logger.warning("onboarding extraction dropped non-object key: %s%s", path, key)
            return _INVALID
        nested = validate_extracted(value, rule, f"{path}{key}.")
        return nested if nested else _INVALID
    if isinstance(rule, list) and len(rule) == 1 and isinstance(rule[0], dict):
        return _validate_object_list(key, value, rule[0], path)
    checked = _validate_leaf(value, rule)
    if checked is _INVALID:
        logger.warning("onboarding extraction dropped ill-typed key: %s%s", path, key)
    return checked


def validate_extracted(delta: dict, schema: dict, path: str = "") -> dict:
    """Keep only fields the prompt config declares, with matching types."""
    clean: dict = {}
    for key, value in delta.items():
        checked = _validate_field(key, value, schema.get(key), path)
        if checked is not _INVALID:
            clean[key] = checked
    return clean


def merge_extracted(base: dict, delta: dict) -> dict:
    merged = dict(base)
    for key, value in delta.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_extracted(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Model call

def _build_messages(
    session: OnboardingSession, locale: str, config: PromptConfig
) -> list[dict]:
    locale_name = LOCALE_NAMES.get(locale, "English")
    system = config.body.replace("{locale_instruction}", locale_name)
    # The schema is the front matter's single source of truth; rendering it
    # here is what stops the model from inventing key names (housing.tenure,
    # utilities, ...) that validation would silently drop.
    system += (
        "\n\n## Extraction schema — the ONLY keys allowed in `extracted`\n"
        "Leaf values show the expected type or the allowed enum values:\n"
        + json.dumps(config.extraction_schema, ensure_ascii=False, indent=2)
    )
    if session.extracted_json:
        # Keeps the model from re-asking settled questions after a resume.
        system += "\n\nAnswers extracted so far:\n" + json.dumps(
            session.extracted_json, ensure_ascii=False
        )
    messages: list[dict] = [{"role": "system", "content": system}]
    for entry in session.transcript_json:
        messages.append({"role": entry["role"], "content": entry["content"]})
    if len(messages) == 1:
        # Anthropic requires at least one non-system message; kick off the
        # opening turn (this synthetic message is not part of the transcript).
        messages.append({"role": "user", "content": "Hi! Start the interview."})
    return messages


def _causes(error: BaseException) -> str:
    """Exception class names along the cause chain — never messages, which
    could carry prompt content."""
    names = []
    current: BaseException | None = error
    while current is not None and len(names) < 5:
        names.append(type(current).__name__)
        current = current.__cause__ or current.__context__
    return " <- ".join(names)


def _call_model(
    messages: list[dict],
    *,
    usage: UsageContext | None = None,
    conversation_id: str | None = None,
) -> InterviewTurn:
    """One structured-output turn on the `onboarding` route, with a single
    retry on any failure (transport, truncation, or validation)."""
    if not get_settings().anthropic_api_key:
        raise OnboardingUnavailable("ANTHROPIC_API_KEY not set")

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return run_structured(
                "onboarding",
                InterviewTurn,
                messages,
                usage=usage,
                conversation_id=conversation_id,
            )
        except Exception as error:
            last_error = error
            logger.warning(
                "onboarding turn call failed (attempt %d): %s", attempt + 1, _causes(error)
            )
    raise OnboardingUnavailable("model call failed after retry") from last_error


# ---------------------------------------------------------------------------
# Session lifecycle

def get_active_session(db: Session, user_id: str) -> OnboardingSession | None:
    return db.scalar(
        select(OnboardingSession)
        .where(
            OnboardingSession.user_id == user_id,
            OnboardingSession.status == "active",
        )
        # Oldest first: deterministic winner if duplicates ever predate the
        # one-active-per-user unique index.
        .order_by(OnboardingSession.created_at)
        .limit(1)
    )


def _append_turn(session: OnboardingSession, role: str, content: str, **extra) -> None:
    # Reassignment (not in-place mutation) so SQLAlchemy change tracking fires.
    session.transcript_json = [*session.transcript_json, {"role": role, "content": content, **extra}]


def _record_assistant_turn(session: OnboardingSession, turn: InterviewTurn) -> None:
    _append_turn(
        session,
        "assistant",
        turn.message,
        input_kind=turn.input_kind,
        options=turn.options,
        done=turn.done,
    )
    if turn.proposal is not None:
        session.proposal_json = SetupProposal(
            **turn.proposal.model_dump(exclude={"income"}),
            income=proposed_income(session.extracted_json),
        ).model_dump()


EXTRA_PAY_MONTHS = [6, 12]


def proposed_income(extracted: dict) -> list[ProposedIncome]:
    """Income schedules from the extracted sources, deterministically: one
    monthly schedule per source, plus a June/December extra pay for 14
    payments a year. Legacy v1/v2 answers (one expected figure) map to a
    single monthly schedule."""
    income = extracted.get("income") or {}
    sources = [s for s in income.get("sources") or [] if isinstance(s, dict)]
    if not sources:
        amount = income.get("expected_monthly_cents")
        if not isinstance(amount, int) or amount <= 0:
            return []
        names = [s for s in income.get("sources") or [] if isinstance(s, str) and s.strip()]
        day = income.get("income_day")
        return [
            ProposedIncome(
                name=names[0].strip() if names else "Nómina",
                amount_cents=amount,
                day=day if isinstance(day, int) and 1 <= day <= 31 else None,
            )
        ]

    extras = sum(1 for s in sources if s.get("payments_per_year") == 14)
    result = []
    for source in sources:
        amount = source.get("amount_cents")
        if not isinstance(amount, int) or amount <= 0:
            continue
        name = (source.get("name") or "").strip() or "Nómina"
        payer = (source.get("payer") or "").strip() or None
        day = source.get("day")
        day = day if isinstance(day, int) and 1 <= day <= 31 else None
        result.append(ProposedIncome(name=name, payer=payer, amount_cents=amount, day=day))
        if source.get("payments_per_year") == 14:
            result.append(
                ProposedIncome(
                    name="Paga extra" if extras == 1 else f"Paga extra {name}",
                    payer=payer,
                    amount_cents=amount,
                    pattern="some_months",
                    months=EXTRA_PAY_MONTHS,
                    day=day,
                )
            )
    return result


def start_session(db: Session, user_id: str, locale: str) -> OnboardingSession:
    """Return the user's active session, creating one (with its opening turn)
    when none exists. Idempotent on an active session."""
    existing = get_active_session(db, user_id)
    if existing is not None:
        return existing

    config = load_prompt_config()
    session = OnboardingSession(
        # Assigned eagerly (not at flush) so the opening LLM call can already
        # carry the session id as its telemetry conversation thread.
        id=str(uuid.uuid4()),
        user_id=user_id,
        prompt_version=config.version,
        transcript_json=[],
        extracted_json={},
    )
    # Opening turn first, persist after — a failed/unconfigured model call
    # must not leave an empty session behind.
    turn = _call_model(
        _build_messages(session, locale, config),
        usage=UsageContext(db, user_id),
        conversation_id=session.id,
    )
    db.add(session)
    _record_assistant_turn(session, turn)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent /start won the one-active-per-user index race
        # (dev StrictMode double-fires effects); adopt the winner.
        db.rollback()
        existing = get_active_session(db, user_id)
        if existing is None:
            raise
        return existing
    return session


def advance(
    db: Session, session: OnboardingSession, user_message: str, locale: str
) -> InterviewTurn:
    """Send the user's reply, persist the exchange, return the next turn.

    A `done` turn without a valid proposal is re-asked once (spec); a second
    failure raises OnboardingUnavailable so the router can fail closed.
    """
    config = load_prompt_config()
    _append_turn(session, "user", user_message)
    usage = UsageContext(db, session.user_id)

    turn = _call_model(
        _build_messages(session, locale, config), usage=usage, conversation_id=session.id
    )
    if turn.done and turn.proposal is None:
        _append_turn(
            session,
            "user",
            "Your last turn set done=true without a proposal. "
            "Repeat it including the full proposal object.",
        )
        turn = _call_model(
            _build_messages(session, locale, config), usage=usage, conversation_id=session.id
        )
        if turn.done and turn.proposal is None:
            raise OnboardingUnavailable("done turn missing proposal after re-ask")

    delta = turn.extracted_delta()
    if delta:
        clean = validate_extracted(delta, config.extraction_schema)
        if clean:
            session.extracted_json = merge_extracted(session.extracted_json, clean)

    _record_assistant_turn(session, turn)
    db.flush()
    return turn


def finalize(
    db: Session, session: OnboardingSession, payload: OnboardingFinalizeRequest
) -> tuple[int, int]:
    """Apply the reviewed proposal: accounts and categories (case-insensitive
    reuse), accepted payees/payers, income schedules, the opening balance,
    preferences document, session completed.

    Runs inside the request transaction (get_db commits/rolls back), so a
    failure anywhere persists nothing. Returns (categories, payees) created.
    """
    _create_accounts(db, session, payload)
    categories_created = 0
    for group_in in payload.category_groups:
        group, _ = ensure_group(db, session.user_id, group_in.name)
        for category_in in group_in.categories:
            _, created = ensure_category(
                db, session.user_id, group.id, category_in.name, category_in.icon
            )
            categories_created += int(created)

    existing_payees = {
        name.lower()
        for name in db.scalars(select(Payee.name).where(Payee.user_id == session.user_id))
    }
    payees_created = 0
    for name in [*payload.payers, *payload.payees]:
        trimmed = name.strip()
        if resolve_payee(db, session.user_id, trimmed) is not None:
            payees_created += int(trimmed.lower() not in existing_payees)
            existing_payees.add(trimmed.lower())

    for income_in in payload.income:
        schedule = IncomeSchedule(user_id=session.user_id)
        apply_schedule(db, session.user_id, schedule, income_in)
        db.add(schedule)

    # Extracted income sources stay in the document as interview memory;
    # planning reads income schedules only.
    PreferencesStore(db).put(session.user_id, dict(session.extracted_json), session.prompt_version)

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.flush()
    return categories_created, payees_created


def _create_accounts(
    db: Session, session: OnboardingSession, payload: OnboardingFinalizeRequest
) -> None:
    """Accepted accounts through the account-creation path (cards get their
    payment category, at zero balance), then the opening balance — when the
    user gave one — into the primary (first) bank account."""
    today = today_madrid()
    primary = None
    for account_in in payload.accounts:
        account = find_by_name(db, session.user_id, account_in.name)
        if account is None:
            account = create_account(
                db, session.user_id, name=account_in.name, type=account_in.type, today=today
            )
        if primary is None and account.type == "bank":
            primary = account
    balance = (session.extracted_json.get("accounts") or {}).get("main_balance_cents")
    if primary is not None and isinstance(balance, int) and balance:
        write_opening_balance(db, primary, balance, today)
