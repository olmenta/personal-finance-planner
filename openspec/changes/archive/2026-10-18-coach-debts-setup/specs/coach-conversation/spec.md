## ADDED Requirements

### Requirement: Managing debts from the conversation

The coach SHALL be able to propose debt changes with these tools, each storing an action with a dry-run preview and the usual revision, confirm, idempotency and undo lifecycle:

- `propose_debt(kind, …)` (kind `debt`), with the debts API fields in plain terms:
  - `card`: the card account by name or type, `plan_monthly` or `target_month`, an optional `minimum`;
  - `loan`: `name`, `installment`, `installments_left`, `next_month`, an optional `day`;
  - `personal`: `name`, `owed`, an optional `lender`, an optional `due_month`;
  - every kind: an optional rate (`rate_percent` with `per: month | year`);
- `propose_debt_change(debt, …only what changes)` (kind `debt_update`);
- `propose_debt_removal(debt)` (kind `debt_delete`): removes the debt's plan; the category and its history stay;
- `propose_debt_extra(amount)` (kind `debt_extra`): sets the monthly extra;
- `propose_debt_conversion(account, installment, installments_left, next_month, day?, rate?)` (kind `debt_convert`): a credit account that is really a loan.

A debt is named by its name, or by its card account or lender. Every write SHALL go through the shared debt operation (debts), so the API's rules apply (`invalid_debt`, `debt_exists`, `outside_planning_horizon`). A refusal SHALL come back in the tool result, and no action is stored.

The preview SHALL show:

- the debt and its plan in words (for changes, before → after);
- its position in the order and its end month, before → after;
- the debt-free month before → after (or that a debt doesn't end within ten years);
- for writes that change a schedule, its category's amount this month and To be assigned before → after;
- `below_minimum` when the plan is under the minimum;
- for `debt_extra`, the debt that gets the extra and, when the cushion isn't met and the extra is above zero, the cushion note with its reason.

Undo SHALL restore the previous state while the debt still holds what the action left:

- `debt`: deletes the debt;
- `debt_update`: restores its fields;
- `debt_delete`: recreates the debt from its recorded fields;
- `debt_extra`: restores the previous extra;
- `debt_convert`: not undoable (the account is archived and money moved; the coach explains how to revert manually).

The coach SHALL ask for a card's minimum and a debt's rate, and SHALL accept "I don't know" by leaving them out.

#### Scenario: A card with a monthly plan

- **WHEN** in October the user says "la Visa debe 634,62 €, cobra 1,5 % al mes y puedo pagar 200 al mes" and has a credit account "Visa" with that balance
- **THEN** the preview shows the card first in the order, ending in January, the debt-free month going from none to January, and Visa's payment category getting 200,00 € this month, and nothing is saved until Confirm

#### Scenario: A loan from a sentence

- **WHEN** the user says "el préstamo del coche son 290,17 € al mes y me quedan 34 cuotas desde noviembre, el día 2"
- **THEN** the proposed loan has installment 290,17 €, 34 installments from November, day 2, with no rate

#### Scenario: Minimum unknown

- **WHEN** the coach asks the card's minimum and the user answers "no lo sé"
- **THEN** the debt is proposed without a minimum and `below_minimum` stays null

#### Scenario: What if I pay more

- **WHEN** the user asks "¿y si pongo 100 € más al mes?" with a card and a loan, and no savings
- **THEN** the preview shows the debt-free month moving earlier, the card as the debt that gets the extra, and the cushion note with its reason; cancelling leaves the extra unchanged

#### Scenario: Undo a change

- **WHEN** the user confirms "la Visa: ahora puedo pagar 250" and taps Undo
- **THEN** the card's plan is back to 200,00 € and the order and debt-free month are as before
