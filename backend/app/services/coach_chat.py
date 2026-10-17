"""The Home conversation (spec: coach-conversation, design D1, D3, D7, D9).

One persisted conversation per user. Sending is idempotent by
`client_message_id`: a resend returns the stored pair, and a resend after a
failed reply reuses the stored user message and retries only the reply.
Each reply is one agent run on the `coach` route with the last messages, a
short snapshot of the month, and the typed tools; its widgets are built by
the server from what the tools produced. Content is never logged.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import clock
from ..llm import UsageContext, run_with_tools
from ..llm.agents import LLMUnavailable
from ..models import CoachAction, CoachConversation, CoachMessage, User
from . import coach_tools, coach_widgets
from . import schedules as sched
from .coach import eur
from .coach_widgets import WidgetRef

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ACTIVE_PROMPT_FILE = "coach_v1.md"
HISTORY_WINDOW = 20
PAGE_SIZE = 30
MAX_TEXT = 8000

AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s?€")


class CoachReply(BaseModel):
    """The model's output: words plus references to widgets — never numbers
    of its own (design D3)."""

    text: str = Field(description="The reply to the user, in their language")
    widgets: list[WidgetRef] = Field(
        default_factory=list, description="Widgets to attach: refs returned by tools in this turn"
    )


class CoachUnavailable(Exception):
    """No key, or the run failed after its retry."""


class PromptConfig(NamedTuple):
    version: str
    body: str


@lru_cache
def load_prompt(filename: str = ACTIVE_PROMPT_FILE) -> PromptConfig:
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    _, front_matter, body = text.split("---", 2)
    return PromptConfig(version=yaml.safe_load(front_matter)["version"], body=body.strip())


# ---- conversation and pages ---------------------------------------------------------


def get_conversation(db: Session, user: User) -> CoachConversation:
    conversation = db.scalar(select(CoachConversation).where(CoachConversation.user_id == user.id))
    if conversation is not None:
        return conversation
    try:
        with db.begin_nested():
            conversation = CoachConversation(user_id=user.id)
            db.add(conversation)
            db.flush()
    except IntegrityError:  # created by a parallel request
        conversation = db.scalar(select(CoachConversation).where(CoachConversation.user_id == user.id))
    return conversation


def _ordered(query, newest_first: bool):
    if newest_first:
        return query.order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
    return query.order_by(CoachMessage.created_at, CoachMessage.id)


def page(db: Session, user: User, before: str | None = None, limit: int = PAGE_SIZE) -> tuple[list, bool]:
    """Messages oldest first, the latest `limit` (before `before`), and
    whether older ones exist."""
    query = select(CoachMessage).where(CoachMessage.user_id == user.id)
    if before:
        anchor = db.scalar(select(CoachMessage).where(CoachMessage.id == before,
                                                      CoachMessage.user_id == user.id))
        if anchor is not None:
            query = query.where(
                (CoachMessage.created_at < anchor.created_at)
                | ((CoachMessage.created_at == anchor.created_at) & (CoachMessage.id < anchor.id))
            )
    rows = list(db.scalars(_ordered(query, newest_first=True).limit(limit + 1)))
    has_more = len(rows) > limit
    return list(reversed(rows[:limit])), has_more


def messages_out(db: Session, user: User, messages: list[CoachMessage]) -> list[dict]:
    widgets = coach_widgets.with_live_actions(db, user, messages)
    return [
        {"id": m.id, "role": m.role, "text": m.text, "widgets": w,
         "client_message_id": m.client_message_id, "reply_to": m.reply_to, "created_at": m.created_at}
        for m, w in zip(messages, widgets)
    ]


# ---- the run -------------------------------------------------------------------------


LANGUAGES = {"es": "Spanish", "en": "English"}


def _context(home, locale: str | None = None) -> str:
    s = home.summary
    lines = [
        f"Snapshot of the user's month {home.month} (computed by Olmenta; for orientation only — "
        "read tools before quoting numbers):",
        f"- the user's app language: {LANGUAGES.get(locale or 'es', 'Spanish')}",
        f"- status: {home.status}" + (f" ({', '.join(r.code for r in home.reasons)})" if home.reasons else ""),
        f"- money in accounts {eur(s.accounts_cents)} = reserved for this month's payments "
        f"{eur(s.covered_cents)} + left to spend {eur(s.left_to_spend_cents)} + saved for the future "
        f"{eur(s.saved_cents)} + unassigned {eur(s.unassigned_cents)}",
        f"- still to pay this month {eur(s.still_to_pay_cents)}, of which short {eur(s.short_cents)}",
        f"- future: {home.future.status}" + (f" from {home.future.month}" if home.future.month else ""),
    ]
    if home.priority:
        lines.append(f"- top suggestion: {home.priority.title}")
    return "\n".join(lines)


def _turn_text(message: CoachMessage) -> str:
    if message.text:
        return message.text
    titles = [(w.get("data") or {}).get("title") or w.get("type", "") for w in message.widgets or []]
    return f"(shown to the user: {', '.join(t for t in titles if t)})" if titles else "(no text)"


def _history(db: Session, user: User, upto: CoachMessage) -> list[dict]:
    """The last messages before `upto`, as alternating turns."""
    rows = list(db.scalars(_ordered(
        select(CoachMessage).where(
            CoachMessage.user_id == user.id, CoachMessage.id != upto.id,
            CoachMessage.created_at <= upto.created_at,
        ), newest_first=True).limit(HISTORY_WINDOW)))
    turns: list[dict] = []
    for m in reversed(rows):
        role = "user" if m.role == "user" else "assistant"
        text = _turn_text(m)
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + text
        else:
            turns.append({"role": role, "content": text})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    if turns and turns[-1]["role"] == "user":  # an earlier message left without a reply
        turns.append({"role": "assistant", "content": "(no reply)"})
    return turns


def _causes(error: BaseException) -> str:
    """Exception class names along the cause chain — never messages, which
    could carry prompt content."""
    names = []
    current: BaseException | None = error
    while current is not None and len(names) < 5:
        names.append(type(current).__name__)
        current = current.__cause__ or current.__context__
    return " <- ".join(names)


def _run(db: Session, user: User, conversation: CoachConversation, messages: list[dict], home):
    """One run with one retry. A failed attempt's proposals are rolled back
    with its savepoint, so a retry never duplicates them."""
    last_error: Exception | None = None
    for attempt in range(2):
        deps = coach_tools.CoachDeps(db=db, user=user, month=sched.current_month(), home=home)
        savepoint = db.begin_nested()
        try:
            reply = run_with_tools(
                "coach", CoachReply, messages, tools=coach_tools.tools(), deps=deps,
                usage=UsageContext(db, user.id), conversation_id=conversation.id,
            )
        except LLMUnavailable as error:
            savepoint.rollback()
            raise CoachUnavailable("no provider key") from error
        except Exception as error:
            savepoint.rollback()
            last_error = error
            logger.warning("coach run failed (attempt %d): %s", attempt + 1, _causes(error))
            continue
        savepoint.commit()
        return reply, deps
    raise CoachUnavailable("coach run failed after retry") from last_error


def _unsourced_amounts(text: str, sources: list[str]) -> int:
    """Euro amounts in the reply that no tool output or the snapshot carried
    (risk check for the evals; only the count is logged)."""
    haystack = " ".join(sources).replace(" ", " ")
    return sum(1 for amount in AMOUNT.findall(text) if amount.replace(" €", "").replace("€", "") not in haystack)


def send(db: Session, user: User, text: str, client_message_id: str) -> tuple[CoachMessage, CoachMessage]:
    """Store the user's message once, run the coach, store its reply.
    Raises CoachUnavailable with the user message kept."""
    conversation = get_conversation(db, user)
    by_client_id = select(CoachMessage).where(
        CoachMessage.user_id == user.id, CoachMessage.client_message_id == client_message_id
    )
    user_message = db.scalar(by_client_id)
    if user_message is None:
        try:
            with db.begin_nested():
                user_message = CoachMessage(
                    user_id=user.id, conversation_id=conversation.id, role="user",
                    text=text[:MAX_TEXT], widgets=[], client_message_id=client_message_id,
                )
                db.add(user_message)
                db.flush()
        except IntegrityError:  # the same send in parallel: it has finished by now
            user_message = db.scalar(by_client_id)
    reply = db.scalar(select(CoachMessage).where(CoachMessage.reply_to == user_message.id))
    if reply is not None:
        return user_message, reply

    from .home import build_home

    home = build_home(db, user)
    user_message.snapshot_version = home.snapshot_version
    prompt = load_prompt()
    context = _context(home, user.locale)
    messages = [
        {"role": "system", "content": prompt.body.replace("{today}", clock.today_madrid().isoformat())},
        {"role": "system", "content": context},
        *_history(db, user, user_message),
        {"role": "user", "content": user_message.text},
    ]
    output, deps = _run(db, user, conversation, messages, home)

    widgets = coach_widgets.build(deps, output.widgets, home.snapshot_version)
    # A proposal the reply forgot to attach is still shown: the user must see
    # what they'd confirm.
    attached = {(w["data"] or {}).get("action_id") for w in widgets}
    for action in deps.actions:
        if action.id not in attached:
            kind = "category_choice" if action.kind == "category" else "action_preview"
            widgets.append(coach_widgets.envelope(kind, {"action_id": action.id}, home.snapshot_version))
    unsourced = _unsourced_amounts(output.text, [context, *deps.tool_outputs])
    if unsourced:
        logger.info("coach reply quoted %d amount(s) not returned by tools", unsourced)
    reply = CoachMessage(
        user_id=user.id, conversation_id=conversation.id, role="assistant",
        text=output.text[:MAX_TEXT], widgets=widgets, reply_to=user_message.id,
        snapshot_version=home.snapshot_version,
    )
    db.add(reply)
    db.flush()
    for action in deps.actions:
        action.message_id = reply.id
    conversation.updated_at = reply.created_at
    db.flush()
    return user_message, reply


def record_result(db: Session, user: User, action: CoachAction) -> CoachMessage:
    """The conversation's record of an applied action (an `action_result`
    widget), created once per action."""
    message_id = (action.result or {}).get("message_id")
    if message_id:
        existing = db.get(CoachMessage, message_id)
        if existing is not None:
            return existing
    from .home import build_home

    conversation = get_conversation(db, user)
    message = CoachMessage(
        user_id=user.id, conversation_id=conversation.id, role="assistant", text="",
        widgets=[coach_widgets.envelope(
            "action_result", {"action_id": action.id, "title": action.preview.get("title", "")},
            build_home(db, user).snapshot_version,
        )],
    )
    db.add(message)
    db.flush()
    action.result = {**(action.result or {}), "message_id": message.id}
    db.flush()
    return message
