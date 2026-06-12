"""Import batch pipeline (design D2–D4).

create_batch runs the whole pipeline synchronously in-request: parse →
normalize → dedupe (in-file, then against existing rows) → AI category
suggestions → staged transactions + batch in one DB transaction. This
function is the future Cloud Tasks worker body — extracting it later changes
the router, not the pipeline. The raw file bytes are parsed in-memory and
never persisted.
"""

import hashlib

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..ingestion import ADAPTERS, NormalizedTransaction
from ..models import Category, ImportBatch, Transaction, User
from . import category_suggestions
from .payees import delete_orphan_payees, resolve_payee

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2_000


class BatchNotStagedError(Exception):
    """Confirm/discard called on a batch that is not in 'staged' state."""


class TooManyRowsError(Exception):
    pass


def import_dedupe_hash(account_id: str, row: NormalizedTransaction) -> str:
    # No salt: identical bank rows are the same row (manual entries salt
    # per-row in the transactions router). external_ref folds in the running
    # balance, so legitimate same-day identical purchases survive.
    raw = (
        f"{account_id}|{row.date.isoformat()}|{row.amount_cents}|"
        f"{row.external_ref or row.description}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def create_batch(
    db: Session, user: User, account_id: str, bank: str, filename: str, content: bytes
) -> ImportBatch:
    adapter = ADAPTERS[bank]
    rows = adapter.parse(content)  # raises StatementFormatError
    if len(rows) > MAX_ROWS:
        raise TooManyRowsError()

    # In-file duplicates collapse first; then one query against existing rows.
    seen: dict[str, NormalizedTransaction] = {}
    skipped = 0
    for row in rows:
        digest = import_dedupe_hash(account_id, row)
        if digest in seen:
            skipped += 1
        else:
            seen[digest] = row
    existing = set(
        db.scalars(
            select(Transaction.dedupe_hash).where(
                Transaction.account_id == account_id,
                Transaction.dedupe_hash.in_(seen.keys()),
            )
        )
    )
    surviving = {digest: row for digest, row in seen.items() if digest not in existing}
    skipped += len(seen) - len(surviving)

    categories = list(
        db.scalars(
            select(Category).where(Category.user_id == user.id, Category.archived.is_(False))
        )
    )
    ordered = list(surviving.items())
    history = category_suggestions.sample_history(db, user.id)
    suggestions = category_suggestions.suggest(
        categories, [row for _, row in ordered], history
    )

    batch = ImportBatch(
        user_id=user.id,
        account_id=account_id,
        source=adapter.source,
        filename=filename[:255],
        status="staged",
        row_count=len(surviving),
        skipped_duplicates=skipped,
    )
    db.add(batch)
    db.flush()
    for index, (digest, row) in enumerate(ordered):
        suggestion = suggestions.get(index, category_suggestions.EMPTY)
        # AI-proposed payee resolves at staging so the review shows the clean
        # name; discard removes payees nothing else references (design D1).
        payee = resolve_payee(db, user.id, suggestion.payee)
        db.add(
            Transaction(
                user_id=user.id,
                account_id=account_id,
                # Income is never categorized — it lands in "ready to assign"
                # (guards against prompt regressions; suggest() also nulls it).
                category_id=suggestion.category_id if row.amount_cents < 0 else None,
                payee_id=payee.id if payee else None,
                date=row.date,
                amount_cents=row.amount_cents,
                currency=row.currency or "EUR",
                description=row.description[:500],
                source=adapter.source,
                import_batch_id=batch.id,
                dedupe_hash=digest,
                status="staged",
            )
        )
    db.flush()
    return batch


def staged_rows(db: Session, batch: ImportBatch) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.import_batch_id == batch.id)
            .order_by(Transaction.date.desc(), Transaction.id)
        )
    )


def _apply_payee_overrides(
    db: Session, user: User, batch: ImportBatch, payee_overrides: dict[str, str]
) -> set[str]:
    """Set user-edited payees on staged rows; returns replaced payee ids."""
    replaced: set[str] = set()
    if not payee_overrides:
        return replaced
    staged = {t.id: t for t in staged_rows(db, batch)}
    for txn_id, name in payee_overrides.items():
        txn = staged.get(txn_id)
        if txn is None:
            continue
        payee = resolve_payee(db, user.id, name[:120])
        new_id = payee.id if payee else None
        if txn.payee_id and txn.payee_id != new_id:
            replaced.add(txn.payee_id)
        txn.payee_id = new_id
    return replaced


def confirm_batch(
    db: Session,
    user: User,
    batch: ImportBatch,
    overrides: dict[str, str | None],
    payee_overrides: dict[str, str] | None = None,
) -> ImportBatch:
    if batch.status != "staged":
        raise BatchNotStagedError()
    valid_ids = {
        c.id for c in db.scalars(select(Category).where(Category.user_id == user.id))
    }
    for txn_id, category_id in overrides.items():
        if category_id is not None and category_id not in valid_ids:
            continue
        db.execute(
            update(Transaction)
            .where(Transaction.id == txn_id, Transaction.import_batch_id == batch.id)
            .values(category_id=category_id)
        )
    replaced_payee_ids = _apply_payee_overrides(db, user, batch, payee_overrides or {})
    db.execute(
        update(Transaction)
        .where(Transaction.import_batch_id == batch.id)
        .values(status="confirmed")
    )
    batch.status = "confirmed"
    db.flush()
    # Replaced AI payee proposals must not linger in autocomplete.
    delete_orphan_payees(db, user.id, replaced_payee_ids)
    return batch


def discard_batch(db: Session, batch: ImportBatch) -> None:
    if batch.status != "staged":
        raise BatchNotStagedError()
    batch_payee_ids: set[str] = set()
    for txn in staged_rows(db, batch):
        if txn.payee_id:
            batch_payee_ids.add(txn.payee_id)
        db.delete(txn)
    db.flush()
    # Rejected AI payee proposals must not linger in autocomplete.
    delete_orphan_payees(db, batch.user_id, batch_payee_ids)
    batch.status = "discarded"
    db.flush()
