# budget-assignment Delta Specification

## ADDED Requirements

### Requirement: Uncategorized spending block

When the month's `uncategorized_count` is greater than zero, the budget screen SHALL render a "Sin categorizar" block above the category groups, in warning style (never the expense red reserved for overspending), showing `uncategorized_cents` and the number of movements and stating that they need a category. The block SHALL offer a "Categorizar ahora" action that requests AI categorization proposals and opens the categorization review on the budget screen itself; applying it SHALL refresh the budget month. When AI proposals are unavailable, the review's empty state SHALL point to categorizing manually from the transactions screen. The block SHALL NOT block assigning, moving money, or any other action, and SHALL disappear once nothing in the month is uncategorized.

#### Scenario: Block shows what needs a category

- **WHEN** June has three uncategorized outflows totaling 74,50 €
- **THEN** the budget screen shows the "Sin categorizar" block with "74,50 €" and "3" above the first group, in warning style

#### Scenario: Categorize from the budget

- **WHEN** the user taps "Categorizar ahora" and applies the proposed categories
- **THEN** the review closes, the categories' spent amounts include those rows, and the block disappears

#### Scenario: Nothing is blocked

- **WHEN** the block is visible
- **THEN** the user can still assign, move money, and cover overspending as usual

#### Scenario: No block when everything is categorized

- **WHEN** the month's `uncategorized_count` is 0
- **THEN** no "Sin categorizar" block is rendered
