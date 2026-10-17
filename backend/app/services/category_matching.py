"""Similar categories and groups for a name (spec: category-matching,
coach-budget-setup design D1).

Before the chat or the MCP server creates a category or a group, this finds
the ones that already look like it, so the user can pick one instead of
splitting money and spending across near-duplicates. Pure string rules,
strongest first; meaning-based matches come from the model as hints."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, CategoryGroup, User
from .names import fold

MAX_MATCHES = 5
MIN_CONTAINS = 3
MIN_WORD = 4
CLOSE_RATIO = 0.8
STOP_WORDS = {"de", "del", "la", "el", "los", "las", "y", "en", "para"}

# Strength per reason, strongest first.
REASONS = {"same_name": 4, "contains": 3, "shared_word": 2, "close_spelling": 1}


@dataclass(frozen=True)
class Match:
    id: str
    name: str
    reason: str
    ratio: float
    group_id: str | None = None
    group_name: str | None = None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", fold(text))


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9ñ]+", normalize(text)) if len(w) >= MIN_WORD and w not in STOP_WORDS}


def reason_for(name: str, candidate: str) -> tuple[str | None, float]:
    a, b = normalize(name), normalize(candidate)
    ratio = SequenceMatcher(None, a, b).ratio()
    if not a or not b:
        return None, ratio
    if a == b:
        return "same_name", ratio
    if min(len(a), len(b)) >= MIN_CONTAINS and (a in b or b in a):
        return "contains", ratio
    if words(a) & words(b):
        return "shared_word", ratio
    if ratio >= CLOSE_RATIO:
        return "close_spelling", ratio
    return None, ratio


def _rank(matches: list[Match]) -> list[Match]:
    return sorted(matches, key=lambda m: (-REASONS[m.reason], -m.ratio, m.name))[:MAX_MATCHES]


def spendable_categories(db: Session, user: User) -> list[Category]:
    """Active categories a person budgets into: not archived, not a card's
    payment category, not in a system group."""
    return list(db.scalars(
        select(Category).join(CategoryGroup, CategoryGroup.id == Category.group_id).where(
            Category.user_id == user.id, Category.archived.is_(False),
            Category.payment_account_id.is_(None), CategoryGroup.system.is_(False),
        ).order_by(CategoryGroup.sort_order, Category.name)
    ))


def user_groups(db: Session, user: User) -> list[CategoryGroup]:
    return list(db.scalars(
        select(CategoryGroup).where(CategoryGroup.user_id == user.id, CategoryGroup.system.is_(False))
        .order_by(CategoryGroup.sort_order)
    ))


def similar_categories(db: Session, user: User, name: str) -> list[Match]:
    found = []
    for c in spendable_categories(db, user):
        reason, ratio = reason_for(name, c.name)
        if reason:
            found.append(Match(c.id, c.name, reason, ratio, c.group_id, c.group.name))
    return _rank(found)


def similar_groups(db: Session, user: User, name: str) -> list[Match]:
    found = []
    for g in user_groups(db, user):
        reason, ratio = reason_for(name, g.name)
        if reason:
            found.append(Match(g.id, g.name, reason, ratio))
    return _rank(found)


def suggest_group(db: Session, user: User, name: str, matches: list[Match] | None = None) -> CategoryGroup | None:
    """The best similar category's group; else the group whose categories
    share the most words with the name; else the last group."""
    groups = user_groups(db, user)
    if not groups:
        return None
    by_id = {g.id: g for g in groups}
    matches = similar_categories(db, user, name) if matches is None else matches
    for m in matches:
        if m.group_id in by_id:
            return by_id[m.group_id]
    wanted = words(name)
    if wanted:
        scores = {
            g.id: sum(len(wanted & words(c.name)) for c in g.categories if not c.archived) + len(wanted & words(g.name))
            for g in groups
        }
        best = max(groups, key=lambda g: scores[g.id])
        if scores[best.id] > 0:
            return best
    return groups[-1]
