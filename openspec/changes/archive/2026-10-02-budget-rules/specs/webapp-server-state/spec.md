# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: Move money mutation

Moving money SHALL go through `POST /api/budget/{month}/moves` via a TanStack Query mutation that optimistically updates the cached month view (source and target assignments and availables; To Be Assigned when the source is "Sin asignar") and replaces the cache with the server's returned view on success. On error the cache SHALL roll back and the UI SHALL surface the machine-readable code as a translated, retryable message.

#### Scenario: Optimistic cover

- **WHEN** the user taps "Cubrir desde Restaurantes" on an overspent Supermercado row
- **THEN** both rows reflect the move immediately, and the server's view replaces the cache when the response arrives

#### Scenario: Rejected move rolls back

- **WHEN** the server answers 422 `insufficient_available` because another device spent the money meanwhile
- **THEN** the rows return to their previous values and an error message invites retrying

### Requirement: Cover prompt after saving a transaction

After a transaction is created or edited from the Add/Edit dialogs, or an import batch is confirmed, the webapp SHALL refetch the affected month (as today) and, when a category touched by that write now has `overspent_cents > 0`, show a non-blocking prompt with the category's `cover_suggestion` ("Supermercado se pasó 50,00 €. Cubrir desde Restaurantes") offering one-tap cover and "Elegir otra" (opens the move-money sheet). The save itself SHALL complete and close its dialog before the prompt appears; dismissing the prompt SHALL leave the overspending visible on the budget screen.

#### Scenario: Overspending expense

- **WHEN** the user adds a 60,00 € Supermercado expense that leaves the category 50,00 € over
- **THEN** the dialog closes as usual and a prompt offers to cover the 50,00 € from the suggested source

#### Scenario: No prompt without overspending

- **WHEN** a saved expense stays within the category's available
- **THEN** no cover prompt appears
