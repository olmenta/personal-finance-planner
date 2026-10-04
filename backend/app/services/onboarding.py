"""AI onboarding interview engine (spec: ai-onboarding, design D1–D5).

The interview script lives in a versioned prompt config
(app/prompts/onboarding_v2.md): YAML front matter declares the prompt
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
from ..models import OnboardingSession, Payee
from ..schemas import OnboardingFinalizeRequest
from ..telemetry import set_llm_conversation
from .accounts import create_account, find_by_name, write_opening_balance
from .category_setup import ensure_category, ensure_group
from .payees import resolve_payee
from .preferences import PreferencesStore

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ACTIVE_PROMPT_FILE = "onboarding_v2.md"

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


class ProposalIncome(BaseModel):
    sources: list[str] = []
    expected_monthly_cents: int | None = None
    income_day: int | None = None


class ProposedAccount(BaseModel):
    name: str
    # Credit cards are accounts (with their payment category); loans stay
    # debt-paydown categories — tracking accounts are out of v1 scope.
    type: Literal["bank", "credit"] = "bank"


class SetupProposal(BaseModel):
    accounts: list[ProposedAccount] = []
    category_groups: list[ProposedGroup]
    payers: list[str] = []
    payees: list[str] = []
    income: ProposalIncome = ProposalIncome()


class InterviewTurn(BaseModel):
    message: str
    input_kind: InputKind = "text"
    options: list[str] = []
    # JSON-encoded object string, not a dict: Anthropic structured output
    # rejects open objects (additionalProperties), and the delta's fields are
    # prompt-config-dynamic by design. Decoded via extracted_delta().
    extracted: str | None = None
    done: bool = False
    proposal: SetupProposal | None = None

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


def _call_model(messages: list[dict]) -> InterviewTurn:
    """One structured-output turn, with a single retry on any failure."""
    import litellm

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise OnboardingUnavailable("ANTHROPIC_API_KEY not set")
    model = settings.anthropic_model
    if "/" not in model:  # bare names default to the Anthropic provider
        model = f"anthropic/{model}"

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = litellm.completion(
                model=model,
                max_tokens=4000,
                messages=messages,
                response_format=InterviewTurn,
                api_key=settings.anthropic_api_key,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty model output")
            return InterviewTurn.model_validate_json(content)
        except Exception as error:  # transport, truncation, or parse failure
            last_error = error
            logger.warning(
                "onboarding turn call failed (attempt %d): %s",
                attempt + 1,
                type(error).__name__,
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
        session.proposal_json = turn.proposal.model_dump()


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
    set_llm_conversation(session.id)
    # Opening turn first, persist after — a failed/unconfigured model call
    # must not leave an empty session behind.
    turn = _call_model(_build_messages(session, locale, config))
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
    set_llm_conversation(session.id)
    _append_turn(session, "user", user_message)

    turn = _call_model(_build_messages(session, locale, config))
    if turn.done and turn.proposal is None:
        _append_turn(
            session,
            "user",
            "Your last turn set done=true without a proposal. "
            "Repeat it including the full proposal object.",
        )
        turn = _call_model(_build_messages(session, locale, config))
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
    reuse), accepted payees/payers, the opening balance, preferences
    document, session completed.

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

    document = dict(session.extracted_json)
    if payload.income is not None:
        document = merge_extracted(
            document, {"income": payload.income.model_dump(exclude_none=True)}
        )
    PreferencesStore(db).put(session.user_id, document, session.prompt_version)

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
