# category-suggestions Delta Specification

## MODIFIED Requirements

### Requirement: On-demand categorization proposals

The API SHALL expose `POST /transactions/suggest-categories` accepting an optional `transaction_ids` list and defaulting to the user's confirmed uncategorized transactions (capped at the 500 newest). It SHALL return proposals `{transaction_id, category_id, payee, confidence}` for rows where the model placed a category or a payee — writing nothing — and an empty list when the AI is unavailable, never an error caused by the AI. `POST /transactions/apply-categories` SHALL accept `{assignments: {transaction_id: {category_id, payee}}}` and apply each valid assignment (owner-scoped, confirmed-only, category validated against the user's tree, payee resolved find-or-create) in one transaction, skipping invalid entries and reporting the applied count. An absent `category_id` SHALL leave the row's category untouched, while an explicit `category_id: null` SHALL clear it — an inflow set back to "Ready to assign" counts as income again.

#### Scenario: Uncategorized rows proposed

- **WHEN** the user has 40 confirmed uncategorized transactions and calls suggest-categories with no body
- **THEN** proposals reference only those rows, each with a category id from the user's tree, an optional proposed payee name, and a confidence level, and no transaction is modified

#### Scenario: Apply writes only what was accepted

- **WHEN** the user applies 25 of 40 proposals, two of which reference rows deleted meanwhile
- **THEN** 23 assignments are written, the response reports the applied count, and the other rows stay untouched

#### Scenario: AI down degrades to empty

- **WHEN** the Anthropic call fails during suggest-categories
- **THEN** the API returns an empty proposal list and no error

#### Scenario: Explicit null returns an inflow to income

- **WHEN** a categorized +12,50 € inflow (a refund) is applied with `category_id: null`, and another row is applied with only a payee
- **THEN** the first row loses its category and counts toward `income_cents`, and the second row keeps its category
