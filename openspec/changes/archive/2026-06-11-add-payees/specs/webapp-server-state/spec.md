# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: Payee entry and rendering

The add-transaction dialog SHALL offer a payee field labeled "Payee" for expenses and "Payer" for incomes, suggesting matches from `GET /api/payees` (case-insensitive substring, free text allowed). Selecting a known payee SHALL prefill the category from the payee's `last_category_id` only when no category is chosen yet — never overriding an explicit choice. The transactions list SHALL render the payee as the row's primary line when present, with the note demoted to secondary text; rows without payee render as before. Transaction mutations SHALL invalidate the payees query alongside the existing invalidations.

#### Scenario: Known payee prefills the category

- **WHEN** the user types "Merc", picks the "Mercadona" suggestion, and has not chosen a category
- **THEN** the category select fills with Mercadona's last-used category, still editable

#### Scenario: Explicit category wins

- **WHEN** the user picks a category first and then selects a known payee
- **THEN** the chosen category stays

#### Scenario: Label follows direction

- **WHEN** the user switches the dialog from Expense to Income
- **THEN** the field label changes from "Payee" to "Payer" and behaves identically

#### Scenario: New payee appears in suggestions

- **WHEN** the user saves a transaction with a brand-new payee name
- **THEN** the next dialog open suggests it without a page reload
