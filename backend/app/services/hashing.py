"""Dedupe hash for rows written by the app (manual entries, opening
balances, transfer twins). Salted per row: identical app-written rows are
legitimate; strict unsalted hashing applies to imported sources (§6.3)."""

import hashlib
from datetime import date


def dedupe_hash(
    account_id: str, txn_date: date, amount_cents: int, description: str | None, salt: str = ""
) -> str:
    raw = f"{account_id}|{txn_date.isoformat()}|{amount_cents}|{description or ''}|{salt}"
    return hashlib.sha256(raw.encode()).hexdigest()
