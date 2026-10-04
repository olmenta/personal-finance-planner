# statement-import Delta Specification

## MODIFIED Requirements

### Requirement: Import batch upload stages transactions

The API SHALL expose `POST /imports` accepting a multipart statement file, a `bank` choice (`bbva` | `sabadell` | `custom`), and an optional `account_id` choosing which of the user's accounts the batch belongs to (defaulting to the main account; a foreign or unknown account returns 404 `account_not_found`). It SHALL run parse → normalize → deduplicate → AI category suggestion synchronously and create an `ImportBatch` plus one transaction per surviving row with `status = "staged"`, `source = "import_bbva" | "import_sabadell" | "import_custom"`, the batch id, and the suggested `category_id` (nullable). Staged rows SHALL NOT affect budget, summary, or the transactions list. Files over the size/row limits SHALL be rejected with a machine-readable code, and the raw file SHALL NOT be persisted.

#### Scenario: Successful upload

- **WHEN** a valid Sabadell `.xls` export with 40 new rows is uploaded
- **THEN** the API returns 201 with a batch of 40 staged transactions, and `GET /budget/{month}` totals are unchanged until confirmation

#### Scenario: Oversize file rejected

- **WHEN** a file larger than the configured limit is uploaded
- **THEN** the API returns 413 with code `file_too_large` and no batch is created

#### Scenario: Statement staged into a chosen account

- **WHEN** the user uploads a Sabadell statement selecting their "Banco Sabadell" account
- **THEN** the batch and all its staged rows carry that account id

#### Scenario: Default account when omitted

- **WHEN** an upload omits `account_id`
- **THEN** the batch lands in the user's main account

## ADDED Requirements

### Requirement: Transfers marked at review

The import review SHALL allow marking a staged row as a transfer to another of the user's accounts (the category selector offers a "Transfers →" group listing the other active accounts). Confirming the batch SHALL create the confirmed twin row in the target account linked by `transfer_pair_id`, with the staged row confirming as the near side; both sides carry no category and no payee. A row marked as transfer SHALL NOT receive a category.

#### Scenario: Outflow marked as transfer

- **WHEN** bank A's statement stages `TRASPASO A CUENTA B −200,00 €` and the user marks it "Transfer → Banco B" before confirming
- **THEN** confirm creates the +200,00 € twin in Banco B, links both rows, and June's income and expenses are unchanged

### Requirement: Twin matching on the counterpart import

When staging rows into an account, the importer SHALL detect staged rows that mirror an existing confirmed transfer twin in that account — equal amount, the twin's date within ±3 days — and attach a non-binding match suggestion to the staged row. Accepting the suggestion at review SHALL adopt the existing twin (the staged row is dropped as a duplicate of it); ignoring it SHALL confirm the row normally. The matcher SHALL never link silently.

#### Scenario: Second bank's side matches the twin

- **WHEN** Banco B's statement is imported and a staged `+200,00 €` row falls within 3 days of the twin created from bank A's side
- **THEN** the review shows a match suggestion on that row, and accepting it leaves exactly one +200,00 € transaction in Banco B (the linked twin)

#### Scenario: Ignored suggestion stays a normal row

- **WHEN** the user ignores a match suggestion
- **THEN** the staged row confirms as an ordinary transaction and the existing twin is untouched

### Requirement: Card payments feed payment-day inference

Card payments confirmed from a bank statement — rows marked (or matched) as transfers into a credit account — SHALL be the history the credit-cards capability uses to suggest a card's `payment_day`. The import SHALL NOT set `payment_day` itself; the suggestion surfaces on the account for the user to accept.

#### Scenario: Two imported card payments produce a suggestion

- **WHEN** the August and September BBVA statements each contain `LIQUIDACION TARJETA` rows marked as transfers to "Visa BBVA" on the 10th and 11th
- **THEN** after confirming the second statement, "Visa BBVA" reports `suggested_payment_day = 10` and its `payment_day` is still unset
