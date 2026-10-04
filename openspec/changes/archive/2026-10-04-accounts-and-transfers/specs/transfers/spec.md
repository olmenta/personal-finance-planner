# transfers Delta Specification

## ADDED Requirements

### Requirement: Transfers are linked twin rows outside the budget plane

A transfer between two of the user's accounts SHALL be persisted as two confirmed transaction rows sharing a `transfer_pair_id`: a negative row in the source account and a positive row of equal magnitude in the destination, both with `category_id = NULL` and `payee_id = NULL`. Transfer rows SHALL be excluded from monthly income and expense/spent aggregates everywhere (budget view, summary, weekly buckets); per-account and all-time balances SHALL include them. `POST /transfers` SHALL accept `from_account_id`, `to_account_id` (distinct, both owned by the user), `amount_cents > 0`, optional `date` (default today) and `note`; same-account transfers SHALL return 422 `same_account`.

#### Scenario: Transfer moves balances, not the budget

- **WHEN** the user transfers 200,00 € from Banco A to Banco B in June
- **THEN** Banco A's balance drops and Banco B's rises by 200,00 €, and June's `income_cents`, `expense_cents`, and every category's `spent_cents` are unchanged

#### Scenario: Credit card payment is a transfer

- **WHEN** the user pays 340,00 € from Banco A to the Tarjeta Visa account
- **THEN** the card balance rises by 340,00 € (toward zero), the card's payment category available drops by 340,00 €, and no expense is recorded — the card's purchases were already categorized at swipe time

### Requirement: Mirrored editing and unlinking

Editing a transfer's `amount_cents`, `date`, or `note` SHALL update both twin rows atomically; deleting a transfer SHALL delete both rows. `PATCH /transactions/{id}` on a row with a `transfer_pair_id` SHALL return 409 `is_transfer` — transfer rows are mutated only through the transfer contract. An unlink operation SHALL clear `transfer_pair_id` on both rows, turning them into two independent uncategorized transactions that immediately count in the budget plane again (the inflow side as income, pending categorization like any row).

#### Scenario: Amount edit mirrors

- **WHEN** a 200,00 € transfer is edited to 250,00 €
- **THEN** the source row reads −250,00 € and the destination row +250,00 €

#### Scenario: Normal PATCH rejected

- **WHEN** a client PATCHes a transfer row through `/transactions/{id}`
- **THEN** the API returns 409 with code `is_transfer`

#### Scenario: Unlink splits the pair

- **WHEN** a mistaken transfer is unlinked
- **THEN** both rows lose their pair id and the positive row starts counting as uncategorized income

### Requirement: Transfer rendering stays neutral

The webapp SHALL render transfer rows with a transfer icon and "Transfer → <account>" (or "← from <account>") in place of the payee, using neutral amount color — the income/expense semantic colors SHALL remain reserved for money entering or leaving the budget. The Add/Edit transaction dialogs SHALL offer a third "Transfer" mode with from-account, to-account, amount, date, and note — no category, no payee.

#### Scenario: Transfer row in the list

- **WHEN** the transactions list shows the 200,00 € transfer from Banco A
- **THEN** the row reads "Transfer → Banco B" with neutral-colored amount and no category chip

#### Scenario: Manual transfer in one dialog

- **WHEN** the user picks the "Transfer" segment in Add transaction
- **THEN** the form shows from/to account pickers, amount, date, and note only, and submitting creates the twin pair
