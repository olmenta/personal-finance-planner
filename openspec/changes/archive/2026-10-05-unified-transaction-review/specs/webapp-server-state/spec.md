# webapp-server-state Delta Specification

## MODIFIED Requirements

### Requirement: AI categorization review flow

The transactions screen SHALL offer a "Review uncategorized" action while confirmed uncategorized transactions exist. Triggering it SHALL open the categorization review (see transaction-review): the same review component the statement import uses, listing every confirmed uncategorized transaction across all months — each with its date, editable note, payee, amount, category picker, "Transfers →" choices and any twin-match suggestion — with the AI's category and payee prefilled as defaults and a confidence badge where the AI made a suggestion. There SHALL be no per-row checkboxes: applying writes the rows whose decision differs from what is stored (a kept AI suggestion counts as a decision) and leaves the others untouched. Applying SHALL invalidate the transactions, payees, budget, summary, overview, plan and accounts queries. With no uncategorized transactions the review SHALL render an actionable empty state, and the AI SHALL never write a category without the user applying it.

#### Scenario: Bulk categorization applied

- **WHEN** the user opens the review over 40 uncategorized rows, keeps 30 AI suggestions, and applies
- **THEN** those 30 transactions show their categories in the list, the other 10 stay uncategorized, and the affected budget bars and dashboard refresh without a page reload

#### Scenario: Low confidence surfaces first

- **WHEN** the review has suggestions with `low` and `high` confidence
- **THEN** the low-confidence rows are listed first with a distinct badge

#### Scenario: AI unavailable still lists the rows

- **WHEN** the AI suggestion call fails or is not configured
- **THEN** the review still lists every uncategorized transaction without suggestions, and the user categorizes them by hand in the same view

#### Scenario: Note edited while reviewing

- **WHEN** the user rewrites a row's note from "BIZUM 8834" to "Cena con Ana" and applies
- **THEN** the transaction's description reads "Cena con Ana" in the list

#### Scenario: Transfer resolved from the review

- **WHEN** a confirmed uncategorized −200,00 € row in BBVA is marked "Transfer → Banco B" in the review and applied
- **THEN** the row becomes the near side of a transfer pair with a +200,00 € twin in Banco B, and neither counts in income or spending
