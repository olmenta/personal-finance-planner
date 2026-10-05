# category-suggestions Specification

## Purpose

AI-assisted category suggestions for ingested transactions: the backend calls the Anthropic API per import batch to propose a category per row, validates the result against the user's real category tree, and degrades gracefully to null suggestions — suggestions are review defaults, never auto-confirmations.
## Requirements
### Requirement: AI category suggestion for ingested rows

The backend SHALL suggest a category per ingested row by calling the Anthropic API (from Python only, never the browser) with the user's category tree, a sample of the user's recent categorized transactions as worked examples (up to ~100 distinct description → category pairs, newest first), and the rows' date, description, amount, and — when the source provided one — the row's free-text category hint, in one structured-output request per batch. Each suggestion SHALL carry a `confidence` of `high`, `medium`, or `low` (missing values degrade to `low`). Each suggestion MAY carry a proposed `payee` — the cleaned merchant/payer name extracted from the description, null when unclear; staged rows resolve it find-or-create so the review shows it before anything is confirmed, and discarding the batch removes payees no other transaction references. Returned category ids SHALL be validated against the user's real categories — unknown ids become null. Any failure of the suggestion call (missing key, rate limit, timeout) SHALL degrade to null suggestions and SHALL NOT fail the import. Suggestions are defaults for human review and SHALL never confirm transactions by themselves.

#### Scenario: Recognizable merchant

- **WHEN** a staged row's description is "MERCADONA VALENCIA" and the user has a "Supermercado" category
- **THEN** the row is staged with `category_id` pointing at "Supermercado"

#### Scenario: History informs the suggestion

- **WHEN** the user has repeatedly categorized "GASOLINERA REPSOL" under "Gasolina" and a new import contains that description
- **THEN** the suggestion request includes that description → category example and the row is suggested as "Gasolina"

#### Scenario: Payee proposed from the raw description

- **WHEN** a staged row's description is "COMPRA TARJ. 4188 MERCADONA VALENCIA"
- **THEN** the row is staged referencing a payee named "Mercadona" for the user to review

#### Scenario: Anthropic unavailable

- **WHEN** the Anthropic API call fails during an import
- **THEN** the batch stages all rows with `category_id = null` and the import succeeds

#### Scenario: Hallucinated category id

- **WHEN** the model returns a category id that does not belong to the user
- **THEN** that row is staged uncategorized

#### Scenario: Custom CSV hint included

- **WHEN** a custom CSV row carries the free-text hint "comida"
- **THEN** the hint is included in the suggestion prompt for that row

