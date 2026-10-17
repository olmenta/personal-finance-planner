## MODIFIED Requirements

### Requirement: Curated tool set

The server SHALL expose exactly these tools: reads `get_budget`, `get_month_overview`, `list_transactions`, `list_categories`, `list_accounts`, `review_uncategorized`, `find_categories`; writes `add_transaction`, `assign`, `set_budget`, `move_money`, `create_category`, `create_group`, `create_transfer`, `apply_review`. Each tool SHALL carry a description stating when to use it, its units and defaults, and what it must not do. Write tools SHALL perform exactly the API write they describe and nothing else.

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

## ADDED Requirements

### Requirement: Similar categories before creating

`create_category(name, group, confirmed_new?)` and `create_group(name, confirmed_new?)` SHALL run the similarity check (category-matching) first:

- **Exact folded match:** nothing is created; the result names the existing category or group to use.
- **Similar ones and no `confirmed_new = true`:** nothing is created. The result lists the similar names and tells the model to ask the user whether to use one of them or create the new one, then to call again with `confirmed_new = true` only if the user chose to create it.
- **No similar ones, or `confirmed_new = true`:** it creates. A `create_category` result also names the group used.

When `group` is omitted, `create_category` SHALL create nothing and return the existing groups with the suggested one, so the model asks the user to pick. `find_categories(name)` SHALL return the similar categories with their groups and the suggested group.

#### Scenario: A near duplicate is caught

- **WHEN** `create_category` is called with `name = "Super"` and "Supermercado" exists
- **THEN** nothing is created and the result lists "Supermercado (Comida)" and asks to confirm with the user

#### Scenario: Created after the user confirms

- **WHEN** the user confirms and `create_category` is called again with `confirmed_new = true` and `group = "Comida"`
- **THEN** the category is created in Comida

#### Scenario: Group not given

- **WHEN** `create_category` is called without `group`
- **THEN** nothing is created and the result lists the existing groups with the suggested one first
