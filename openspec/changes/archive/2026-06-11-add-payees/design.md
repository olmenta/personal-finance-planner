# Design — Payees

## Context

`Transaction.description` is the only "who" field — free text written by the user or by bank adapters ("Consum alaquas av.blasco … — Pago con tarjeta"). The schema has no payee concept; project-definition §6.4 anticipates one indirectly via YNAB-style budgeting but v1 shipped without it. Entry speed is the core UX promise (< 5 s), and the add dialog already prefetches categories. Alembic is established (two revisions); `edit-delete-transactions` (in flight) will add PATCH on transactions and must pick up the payee field when both land.

## Goals / Non-Goals

**Goals:**

- One payee entity for both directions — "Payee" on expenses, "Payer" on incomes is labeling, not modeling (YNAB semantics).
- Zero-friction creation: typing a new name creates the payee; typing a known one reuses it regardless of casing.
- Category memory: choosing a known payee prefills the category the user last used with it.

**Non-Goals:**

- Payee CRUD UI (rename, merge, delete) — v1.x once lists grow messy.
- Auto-extracting payees from bank imports — raw bank strings ("4188…CONSUM ALAQUAS") would pollute the list; a cleanup/mapping pass belongs with the AI categorization work.
- Per-payee default beyond "last used" (no frequency weighting yet).

## Decisions

### D1 — Real table, not a string column

`Payee(id, user_id, name)` with a per-user case-insensitive unique index (`func.lower(name)`), plus nullable `transactions.payee_id` FK. A plain string column on transactions would give autocomplete via `DISTINCT`, but no stable identity — renames, merges, and per-payee memory all need an id sooner or later, and the migration is one small table now versus a backfill later. Description stays as the optional note; the two fields stop competing.

### D2 — Find-or-create inside transaction writes

`TransactionCreate` (and `TransactionUpdate` when it lands) gains optional `payee: str` (≤120 chars, trimmed). The handler resolves it case-insensitively within the user's payees and creates on miss — no `POST /payees`. Payees are born from use, exactly like YNAB; an empty/omitted field leaves `payee_id` null. Sending `payee: ""` on update clears it. Alternative rejected: client sends `payee_id` — forces a create-payee round-trip before every new-payee entry, breaking the 5-second flow.

### D3 — `GET /payees` carries the category memory

Returns `[{id, name, last_category_id}]` ordered by most recent use; `last_category_id` is the category of the user's newest confirmed transaction with that payee (null when none). One query with a window/group-by; the list is small (typically < a few hundred) so the client filters locally for autocomplete. Cached under `["payees"]`, invalidated by transaction mutations. Alternative rejected: server-side `?q=` search — needless round-trips for a list this size.

### D4 — UI: one field, direction-driven label, prefill not override

In `AddTransactionDialog` the field sits above the description, labeled "Payee" (Expense) / "Payer" (Income), implemented as a text input with a local-filtered suggestion list from `["payees"]` (match on substring, case-insensitive; free text allowed). Selecting a suggestion whose `last_category_id` exists **and** the category field is still empty prefills the category — never overwrites an explicit choice. Transactions list rows render payee as the primary line when present (description drops to the secondary line next to the source); rows without payee render as today. `TransactionOut` gains `payee_id` and `payee_name` (joined server-side — saves a client join for a constantly-rendered field).

### D5 — Imports leave payee null

Bank adapters keep writing description only. The import review and AI suggestion flows are untouched; when payee mapping arrives (v1.x), it can propose payees from descriptions through the same review pattern. The `payees` capability spec states this boundary so the import specs stay clean.

## Risks / Trade-offs

- [Payee list accumulates typos without rename/merge] → case-insensitive matching catches the main source; management UI is an explicit v1.x follow-up.
- [Four in-flight changes touch `bff-proxy`/`transactions-api` requirements] → deltas modify different requirements where possible; sync-time merge step in tasks (same protocol as the other changes).
- [`last_category_id` query cost grows with history] → single indexed query per list call; revisit with a denormalized column only if it ever shows up in latency.
- [Edit dialog (in-flight) ships without payee if it lands first] → tasks include a reconciliation item: whichever lands second wires payee into the edit dialog.

## Migration Plan

1. Migration (`payees` + FK) — additive, deployable alone.
2. Backend: find-or-create in create (and edit if landed), `GET /payees`, output shape, tests.
3. BFF + api.ts.
4. Dialog field + row rendering.
Rollback: revert webapp commit; endpoints additive; migration has a clean `downgrade()`.

## Open Questions

- None blocking.
