# statement-import Delta Specification

## MODIFIED Requirements

### Requirement: Review, confirm, and discard

The API SHALL expose `GET /imports/{id}` returning the batch (status, `row_count`, `skipped_duplicates`, staged rows), `POST /imports/{id}/confirm` accepting per-row category overrides and flipping the batch's staged rows to `confirmed`, and `DELETE /imports/{id}` deleting the staged rows and marking the batch `discarded`. Per-row category selection SHALL be available for positive rows as well as negative ones: a positive row defaults to uncategorized ("Ready to assign" — it confirms as income) and MAY be assigned a category during review, which confirms it as a refund (category activity). AI category suggestions MAY propose a category for a positive row whose cleaned payee matches the user's categorization history, and SHALL leave unmatched positive rows unsuggested. Confirmed rows SHALL immediately count in budget, summary, and the transactions list. Confirming or discarding a batch that is not `staged` SHALL return 409 with a machine-readable code.

#### Scenario: Confirm with override

- **WHEN** the user confirms a batch overriding one row's category from the AI suggestion to "Ocio"
- **THEN** all rows become `confirmed`, the overridden row carries "Ocio", and the month's budget `spent_cents` reflects the batch

#### Scenario: Imported refund categorized at review

- **WHEN** a statement stages `ABONO MERCADONA +12,50` and the user assigns it the Supermercado category before confirming
- **THEN** the confirmed row carries Supermercado, the month's Supermercado `spent_cents` drops by 12,50 €, and `income_cents` does not include it

#### Scenario: Positive row left uncategorized is income

- **WHEN** a staged positive row is confirmed without a category
- **THEN** it counts in the month's `income_cents` (To Be Assigned)

#### Scenario: Discard a batch

- **WHEN** the user discards a staged batch
- **THEN** its staged transactions are deleted, the batch is `discarded`, and a later re-upload of the same file stages the rows again

#### Scenario: Double confirm rejected

- **WHEN** confirm is called on an already-confirmed batch
- **THEN** the API returns 409 with code `batch_not_staged`
