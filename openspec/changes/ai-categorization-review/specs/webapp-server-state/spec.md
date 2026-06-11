# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: AI categorization review flow

The transactions screen SHALL offer a "Suggest categories" action when confirmed uncategorized transactions exist. Triggering it SHALL request proposals and open a review dialog listing each proposed row (date, description, amount, editable category select prefilled with the proposal, confidence badge) with per-row checkboxes defaulting to checked and low-confidence rows sorted first. Applying SHALL post only the checked rows (with any overrides) to the apply endpoint and invalidate the transactions query plus the budget and summary queries for every affected month. An empty proposal list (nothing uncategorized, or AI unavailable) SHALL render an actionable empty state, never a dead end, and the AI SHALL never write a category without the user applying it.

#### Scenario: Bulk categorization applied

- **WHEN** the user runs "Suggest categories" over 40 uncategorized rows and applies 30 of them
- **THEN** those 30 transactions show their categories in the list and the affected months' budget bars and dashboard refresh without a page reload

#### Scenario: Low confidence surfaces first

- **WHEN** proposals include `low` and `high` confidence rows
- **THEN** the review dialog lists the low-confidence rows first with a distinct badge

#### Scenario: AI unavailable

- **WHEN** the suggestion request returns no proposals
- **THEN** the dialog explains nothing could be suggested right now and points to manual categorization instead of showing an error wall
