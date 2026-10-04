# credit-cards Delta Specification

## ADDED Requirements

### Requirement: Every credit account has a payment category

Creating an account with `type = "credit"` SHALL create, in the same transaction, a system-managed payment category named after the card (e.g. "Pago Visa BBVA") inside a system category group "Tarjetas de crédito" (created on first need), linked to the account through `Category.payment_account_id`. Payment categories SHALL NOT be deletable or re-parented through category CRUD, SHALL be renamed when the account is renamed, and SHALL be archived when the account is archived. Assigning money to a payment category SHALL work like any other assignment (it is how pre-existing card debt gets paid down).

#### Scenario: Card creation brings its payment category

- **WHEN** the user creates `{name: "Visa BBVA", type: "credit"}`
- **THEN** the budget view shows a "Tarjetas de crédito" group containing "Pago Visa BBVA" with zero assigned and zero available

#### Scenario: Payment category cannot be deleted directly

- **WHEN** a client tries to delete a payment category through the categories API
- **THEN** the API returns 409 with code `payment_category_locked`

### Requirement: Budgeted card spending moves to the payment category

For each month, categorized card activity SHALL move money from its spending category to the card's payment category, derived at read time (never stored as transactions). Per spending category C and credit account K in month M: the category's available before card activity is `assigned + rollover − net non-card activity`; the funded move is the card spending in C capped at that available when it is positive (zero otherwise). A categorized inflow on the card (a refund) SHALL move its full amount back from the payment category to C. The payment category's available SHALL be `assigned + rollover + Σ funded moves − payments`, where payments are transfer inflows into K in the month. Moves between categories SHALL NOT change To Be Assigned.

#### Scenario: Budgeted purchase is set aside for the card

- **WHEN** Supermercado has 400,00 € available and the user pays 200,00 € for groceries with "Visa BBVA"
- **THEN** Supermercado's available drops to 200,00 €, "Pago Visa BBVA" available rises to 200,00 €, the card balance is −200,00 €, and To Be Assigned is unchanged

#### Scenario: Paying the card uses the set-aside money

- **WHEN** the user then transfers 200,00 € from BBVA to "Visa BBVA"
- **THEN** the card balance returns to 0, "Pago Visa BBVA" available returns to 0, and Supermercado is unchanged (the spending was counted at purchase)

#### Scenario: Card refund reverses the move

- **WHEN** a +12,50 € refund categorized to Supermercado posts on "Visa BBVA"
- **THEN** Supermercado's available rises by 12,50 € and "Pago Visa BBVA" available drops by 12,50 €

### Requirement: Credit overspending becomes card debt

Card spending that exceeds the category's available SHALL NOT be moved to the payment category; the unfunded part is credit overspending. The view SHALL report it per category as `credit_overspent_cents`, distinct from cash overspending. At month end the credit-overspent amount SHALL NOT carry into the category's next-month rollover: the category starts the next month without it, and the amount remains as card debt not covered by the payment category.

#### Scenario: Overspending on the card

- **WHEN** Supermercado has 150,00 € available and the user spends 200,00 € on "Visa BBVA"
- **THEN** only 150,00 € moves to "Pago Visa BBVA", the category reports `credit_overspent_cents = 5000`, and the card owes 50,00 € more than its payment category holds

#### Scenario: Credit overspending does not carry forward

- **WHEN** that month closes without the overspending being covered
- **THEN** next month Supermercado's rollover excludes the 50,00 € and the card's uncovered debt stays at 50,00 €

#### Scenario: Covering the overspending funds the card

- **WHEN** the user moves 50,00 € from Restaurantes to Supermercado in the same month
- **THEN** the full 200,00 € moves to "Pago Visa BBVA" and `credit_overspent_cents` is 0

### Requirement: Card debt and coverage are visible

`GET /accounts` SHALL report for credit accounts, besides the derived `balance_cents`, the payment category's `payment_available_cents` and `uncovered_debt_cents = max(0, −balance_cents − payment_available_cents)`. The webapp SHALL present a credit balance as an amount owed ("Debes 200,00 €") in neutral color rather than a raw negative number; internally the balance stays negative.

#### Scenario: Fully covered card

- **WHEN** "Visa BBVA" has balance −200,00 € and its payment category holds 200,00 €
- **THEN** the account reports `uncovered_debt_cents = 0` and the accounts list reads "Debes 200,00 €" without a debt warning

#### Scenario: Pre-existing debt is uncovered

- **WHEN** a card is created with a debt of 340,00 € and nothing has been assigned to its payment category
- **THEN** the account reports `uncovered_debt_cents = 34000`

### Requirement: Card payment day

Credit accounts SHALL carry an optional `payment_day` (1–31, the day of the month the card is charged to the bank account). The user MAY set it when creating or editing the account. When it is unset and at least two confirmed transfers into the card fall on the same day of the month (±2 days), the backend SHALL expose a `suggested_payment_day` on the account for the user to accept; it SHALL never be applied silently. The payment day SHALL be exposed so future coverage checks can compare the payment category against the next charge date.

#### Scenario: Payment day set at creation

- **WHEN** the user creates "Visa BBVA" with `payment_day = 10`
- **THEN** `GET /accounts` reports `payment_day = 10` for it

#### Scenario: Payment day inferred from statements

- **WHEN** "Visa BBVA" has no `payment_day` and confirmed payments into it landed on 10 August and 11 September
- **THEN** `GET /accounts` reports `suggested_payment_day = 10` (the earliest day of the matching cluster) and `payment_day` stays null until the user accepts it

#### Scenario: Not enough history

- **WHEN** a card has fewer than two payments
- **THEN** `suggested_payment_day` is null
