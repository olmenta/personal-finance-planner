"""Resolving a list of transactions (unified-transaction-review design D1).

One implementation for both reviews: the staged rows of an import batch and
the user's confirmed uncategorized rows. A row is resolved with a category
(or none), a payee, a note, a transfer to another account, or by adopting
the existing transfer twin it mirrors. Callers choose the rows; this module
never decides which rows a user may touch.
"""

from datetime import timedelta
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Category, Transaction, User
from ..schemas import TwinMatch
from .payees import resolve_payee
from .transfers import annotate_counterparts, link_existing

MATCH_WINDOW_DAYS = 3


class TwinMatchSuggestion(NamedTuple):
    twin: Transaction
    other_account_id: str | None


def twin_match_out(match: TwinMatchSuggestion) -> TwinMatch:
    return TwinMatch(
        transaction_id=match.twin.id,
        pair_id=match.twin.transfer_pair_id or "",
        other_account_id=match.other_account_id or "",
        date=match.twin.date,
    )


class Decisions(NamedTuple):
    """The review's decision maps, keyed by transaction id."""

    overrides: dict[str, str | None]  # category id, or None to clear
    payee_overrides: dict[str, str]  # "" clears
    note_overrides: dict[str, str | None]  # None or "" clears
    transfer_overrides: dict[str, str]  # other account id
    accept_matches: list[str]


def twin_matches(db: Session, rows: list[Transaction]) -> dict[str, TwinMatchSuggestion]:
    """Row id -> the existing transfer twin it seems to mirror.

    Candidates are confirmed transfer rows in the row's account with the same
    signed amount, dated within ±3 days, still app-written (an adopted twin
    takes the row's source and never matches again). Closest date wins; one
    twin is never suggested for two rows. Suggestions only — the review
    decides.
    """
    by_account: dict[str, list[Transaction]] = {}
    for row in rows:
        if row.transfer_pair_id is None:
            by_account.setdefault(row.account_id, []).append(row)
    result: dict[str, TwinMatchSuggestion] = {}
    for account_id, account_rows in by_account.items():
        first = min(t.date for t in account_rows) - timedelta(days=MATCH_WINDOW_DAYS)
        last = max(t.date for t in account_rows) + timedelta(days=MATCH_WINDOW_DAYS)
        twins = annotate_counterparts(
            db,
            list(
                db.scalars(
                    select(Transaction)
                    .where(
                        Transaction.account_id == account_id,
                        Transaction.status == "confirmed",
                        Transaction.transfer_pair_id.is_not(None),
                        Transaction.source == "manual",
                        Transaction.date >= first,
                        Transaction.date <= last,
                    )
                    .order_by(Transaction.date, Transaction.id)
                )
            ),
        )
        used: set[str] = set()
        for row in account_rows:
            candidates = [
                t
                for t in twins
                if t.id not in used
                and t.amount_cents == row.amount_cents
                and abs((t.date - row.date).days) <= MATCH_WINDOW_DAYS
            ]
            if not candidates:
                continue
            twin = min(candidates, key=lambda t: (abs((t.date - row.date).days), t.date, t.id))
            used.add(twin.id)
            result[row.id] = TwinMatchSuggestion(twin, twin.transfer_account_id)
    return result


def _apply_categories(
    db: Session, user: User, rows: dict[str, Transaction], overrides: dict[str, str | None]
) -> set[str]:
    """Returns the ids of the rows whose category was set or cleared."""
    if not overrides:
        return set()
    valid = set(db.scalars(select(Category.id).where(Category.user_id == user.id)))
    applied: set[str] = set()
    for txn_id, category_id in overrides.items():
        txn = rows.get(txn_id)
        if txn is None or (category_id is not None and category_id not in valid):
            continue
        txn.category_id = category_id
        applied.add(txn_id)
    return applied


def _apply_payees(
    db: Session, user: User, rows: dict[str, Transaction], payee_overrides: dict[str, str]
) -> set[str]:
    """Set edited payees; returns the payee ids that were replaced."""
    replaced: set[str] = set()
    for txn_id, name in payee_overrides.items():
        txn = rows.get(txn_id)
        if txn is None:
            continue
        payee = resolve_payee(db, user.id, name[:120])
        new_id = payee.id if payee else None
        if txn.payee_id and txn.payee_id != new_id:
            replaced.add(txn.payee_id)
        txn.payee_id = new_id
    return replaced


def _apply_notes(rows: dict[str, Transaction], note_overrides: dict[str, str | None]) -> None:
    """The note is the row's description: an edit replaces the bank text.
    The dedupe hash is fixed, so re-imports still collide."""
    for txn_id, note in note_overrides.items():
        txn = rows.get(txn_id)
        if txn is not None:
            txn.description = (note or "").strip()[:500] or None


def _adopt_matches(
    db: Session, rows: dict[str, Transaction], accepted: list[str]
) -> tuple[set[str], set[str]]:
    """Accepted suggestions: the row is a duplicate of the existing twin —
    drop it, and give the twin its hash and source so a re-import collides
    with it and it never matches again. Returns (dropped payee ids, adopted
    row ids)."""
    candidates = [rows[i] for i in accepted if i in rows]
    if not candidates:
        return set(), set()
    matches = twin_matches(db, candidates)
    dropped: set[str] = set()
    adopted: set[str] = set()
    for row in candidates:
        match = matches.get(row.id)
        if match is None:
            continue
        digest, source = row.dedupe_hash, row.source
        if row.payee_id:
            dropped.add(row.payee_id)
        db.delete(row)
        db.flush()
        match.twin.dedupe_hash = digest
        match.twin.source = source
        adopted.add(row.id)
    db.flush()
    return dropped, adopted


def _mark_transfers(
    db: Session, user: User, rows: dict[str, Transaction], transfer_overrides: dict[str, str]
) -> tuple[set[str], set[str]]:
    """Rows marked "Transfer → <account>" become the near side of a pair;
    the confirmed twin lands in the other account. Invalid targets (the
    row's own account, foreign, archived) are skipped like invalid category
    overrides. Returns (dropped payee ids, marked row ids)."""
    if not transfer_overrides:
        return set(), set()
    targets = {
        a.id: a
        for a in db.scalars(
            select(Account).where(Account.user_id == user.id, Account.archived.is_(False))
        )
    }
    dropped: set[str] = set()
    marked: set[str] = set()
    for txn_id, account_id in transfer_overrides.items():
        txn, target = rows.get(txn_id), targets.get(account_id)
        if txn is None or target is None or txn.transfer_pair_id or target.id == txn.account_id:
            continue
        if txn.payee_id:
            dropped.add(txn.payee_id)
        link_existing(db, txn, target)
        marked.add(txn_id)
    return dropped, marked


def apply_decisions(
    db: Session, user: User, rows: list[Transaction], decisions: Decisions
) -> tuple[set[str], int]:
    """Apply the review's decisions to `rows` (entries for other rows are
    ignored). Returns (payee ids that lost references, rows written)."""
    by_id = {t.id: t for t in rows}
    touched = _apply_categories(db, user, by_id, decisions.overrides)
    replaced = _apply_payees(db, user, by_id, decisions.payee_overrides)
    touched |= {i for i in decisions.payee_overrides if i in by_id}
    # Before marking transfers: the twin copies the near row's note.
    _apply_notes(by_id, decisions.note_overrides)
    touched |= {i for i in decisions.note_overrides if i in by_id}
    # Adopt before marking: an accepted row must not also become a new pair.
    dropped, adopted = _adopt_matches(db, by_id, decisions.accept_matches)
    replaced |= dropped
    for row_id in adopted:
        by_id.pop(row_id, None)
    touched |= adopted
    dropped, marked = _mark_transfers(db, user, by_id, decisions.transfer_overrides)
    replaced |= dropped
    touched |= marked
    db.flush()
    return replaced, len(touched)
