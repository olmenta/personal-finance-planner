# category-suggestions Delta Specification

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: On-demand categorization proposals

The API SHALL expose `POST /transactions/suggest-categories` accepting an optional `transaction_ids` list and defaulting to the user's confirmed uncategorized transactions (capped at the 500 newest). It SHALL return proposals `{transaction_id, category_id, payee, confidence}` for rows where the model placed a category or a payee — writing nothing — and an empty list when the AI is unavailable, never an error caused by the AI. `POST /transactions/apply-categories` SHALL accept `{assignments: {transaction_id: {category_id, payee}}}` and apply each valid assignment (owner-scoped, confirmed-only, category validated against the user's tree, payee resolved find-or-create) in one transaction, skipping invalid entries and reporting the applied count.

#### Scenario: Uncategorized rows proposed

- **WHEN** the user has 40 confirmed uncategorized transactions and calls suggest-categories with no body
- **THEN** proposals reference only those rows, each with a category id from the user's tree, an optional proposed payee name, and a confidence level, and no transaction is modified

#### Scenario: Apply writes only what was accepted

- **WHEN** the user applies 25 of 40 proposals, two of which reference rows deleted meanwhile
- **THEN** 23 assignments are written, the response reports the applied count, and the other rows stay untouched

#### Scenario: AI down degrades to empty

- **WHEN** the Anthropic call fails during suggest-categories
- **THEN** the API returns an empty proposal list and no error
