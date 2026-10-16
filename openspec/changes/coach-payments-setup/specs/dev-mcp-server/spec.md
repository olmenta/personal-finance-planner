## MODIFIED Requirements

### Requirement: Curated tool set

The server SHALL expose exactly these tools: reads `get_budget`, `get_month_overview`, `list_transactions`, `list_categories`, `list_accounts`, `review_uncategorized`, `find_categories`, `list_payments`; writes `add_transaction`, `assign`, `set_budget`, `move_money`, `create_category`, `create_group`, `add_payment`, `update_payment`, `delete_payment`, `create_transfer`, `apply_review`. Each tool SHALL carry a description stating when to use it, its units and defaults, and what it must not do. Write tools SHALL perform exactly the API write they describe and nothing else.

#### Scenario: Expense added from a sentence

- **WHEN** the developer says "gasté 40 en Mercadona" and the host calls `add_transaction` with `amount = 40`, `kind = "expense"`, `category = "Supermercado"`, `payee = "Mercadona"`
- **THEN** a −40,00 € confirmed transaction exists in Supermercado for today in the main account, and the tool result states it

#### Scenario: Money moved from To Be Assigned

- **WHEN** `move_money` is called with `amount = 50` and `to_category = "Restaurantes"` and no `from_category`
- **THEN** 50,00 € move from To Be Assigned to Restaurantes in the current month

#### Scenario: Uncategorized transactions resolved

- **WHEN** `review_uncategorized` lists a row and `apply_review` is called for its id with `category = "Supermercado"` and `note = "Compra semanal"`
- **THEN** the transaction is categorized with that note, with the same semantics as the webapp's review

#### Scenario: A budget set in one call

- **WHEN** `set_budget` is called with Supermercado 300, Gasolina 80 and Ocio 50
- **THEN** the three assignments are set for the current month, and the result lists each one and the new To be assigned

#### Scenario: A cash expense

- **WHEN** `add_transaction` is called with `account = "efectivo"` and the user has one cash account named "Efectivo"
- **THEN** the expense is recorded in that account

#### Scenario: A payment added from a sentence

- **WHEN** the host calls `add_payment` with `category = "Alquiler"`, `name = "Alquiler"`, `amount = 850`, `pattern = "monthly"`, `day = 1`
- **THEN** the payment is saved, the current month's assignment for Alquiler becomes 850,00 €, and the result states the payment in words and the new monthly amount

#### Scenario: A debt's payment refused

- **WHEN** `update_payment` targets a loan installment managed from What you owe
- **THEN** nothing changes and the result says to change it in What you owe
