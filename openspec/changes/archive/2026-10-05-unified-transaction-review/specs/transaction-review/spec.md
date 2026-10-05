# transaction-review Specification

## ADDED Requirements

### Requirement: Review of uncategorized transactions

The API SHALL expose `POST /transactions/review` returning the user's confirmed transactions without a category, excluding transfer rows and opening-balance rows, newest first and capped at 500, across all months. Each row SHALL carry its transaction fields plus `suggested_category_id`, `suggested_payee` and `confidence` (`high` | `medium` | `low`) from the category-suggestion service — all null when the AI is not configured, fails, or has no suggestion — and a `match` (the existing confirmed transfer twin it seems to mirror, or null) computed with the statement import's twin-matching rule (same account, same signed amount, twin dated within ±3 days, twin still app-written, closest date wins, one twin per row). The request SHALL NOT write anything, and an AI failure SHALL NOT fail it.

#### Scenario: Every uncategorized row is listed

- **WHEN** the user has 12 confirmed uncategorized transactions over three months, one transfer pair and a card's opening balance
- **THEN** the review lists exactly the 12 transactions, newest first

#### Scenario: AI suggestion as a default

- **WHEN** the AI proposes "Supermercado" with high confidence for a "MERCADONA" row
- **THEN** that row carries `suggested_category_id` of Supermercado and `confidence = "high"`, and its stored category is still null

#### Scenario: Works without AI

- **WHEN** no AI key is configured
- **THEN** the review returns every uncategorized row with null suggestions and no error

#### Scenario: Twin match on a confirmed row

- **WHEN** a manual transfer of 200,00 € from BBVA to Banco B exists on 10 June and Banco B holds a confirmed uncategorized +200,00 € row dated 12 June
- **THEN** that row's `match` names the twin and BBVA as the other account

### Requirement: Applying review decisions

The API SHALL expose `POST /transactions/review/apply` accepting the statement import's decision maps — `overrides` (row → category id, or null to clear), `payee_overrides` (row → name; "" clears), `note_overrides` (row → note; null or "" clears the description), `transfer_overrides` (row → another of the user's active accounts) and `accept_matches` (rows whose match was accepted) — and applying them in one transaction with the import's semantics: categories validated against the user's tree, payees resolved find-or-create, notes replacing the description without touching the dedupe hash, a transfer-marked row becoming the near side of a new pair with a confirmed twin in the target account (category and payee cleared), and an accepted match deleting the row while the existing twin takes its dedupe hash and source. Only the user's confirmed, uncategorized, non-transfer rows SHALL be affected; unknown, foreign or invalid entries SHALL be skipped without failing the request, and the response SHALL report how many rows were written. Rows absent from every map SHALL stay untouched.

#### Scenario: Category, payee and note applied

- **WHEN** a row gets "Supermercado", payee "Mercadona" and note "Compra semanal"
- **THEN** the transaction stores all three and counts as Supermercado spending

#### Scenario: Transfer marked on a confirmed row

- **WHEN** a confirmed uncategorized −200,00 € BBVA row is applied with `transfer_overrides` to Banco B
- **THEN** it is linked to a new confirmed +200,00 € twin in Banco B, both without category or payee, and the month's income and spending exclude them

#### Scenario: Accepted match removes the duplicate

- **WHEN** the row matched to an existing twin is applied in `accept_matches`
- **THEN** the row is deleted, the twin keeps its pair, and Banco B holds exactly one +200,00 € transaction

#### Scenario: Foreign or categorized rows ignored

- **WHEN** the maps reference another user's row or an already categorized row
- **THEN** those entries are skipped and the rest are applied

### Requirement: One review component for imports and uncategorized transactions

The webapp SHALL use a single review component for the statement import review and the categorization review. Each row SHALL offer the same controls — editable note, payee with suggestions, category picker (see category-picker) with "Ready to assign"/"Uncategorized", "Transfers →" to the user's other active accounts (relative to that row's own account), and the twin-match chip with "Link them" / "Keep separate" / "Undo" — and the same behavior: no per-row checkboxes, the suggestion (the import's staged category, or the review's AI suggestion) as the row's default with a badge, and only the edited row re-rendering while typing. The two entry points SHALL differ only in their source and their actions: the import confirms or discards a batch; the categorization review applies its decisions.

#### Scenario: Same controls in both reviews

- **WHEN** the user opens the import review and the categorization review
- **THEN** both list rows with the same note, payee, category, transfer and match controls

#### Scenario: Typing stays responsive in either review

- **WHEN** either review lists 150 rows and the user types a note in one of them
- **THEN** every keystroke appears immediately
