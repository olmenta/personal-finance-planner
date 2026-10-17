## ADDED Requirements

### Requirement: Setting up payments from the conversation

The coach SHALL be able to propose payments (payment schedules) with these tools, each storing an action with a dry-run preview and the usual revision, confirm, idempotency and undo lifecycle:

- `propose_payment(category, name, amount, pattern, months?, month?, every_n?, start_month?, once_month?, count?, day?, estimated?)` (kind `payment`): a new payment in an existing category. A category that doesn't exist SHALL go through `propose_category` with the payment as its follow-up.
- `propose_payment_change(payment, changes)` (kind `payment_update`): the payment is named by its name or its category; ambiguous names are an error listing the candidates.
- `propose_payment_removal(payment)` (kind `payment_delete`).

Every write SHALL go through the shared payment operation (payment-schedules), so the editor's rules apply:

- `invalid_schedule` for missing or contradictory fields;
- `outside_planning_horizon`;
- `managed_by_debt`, with a pointer to What you owe;
- `card_plan_exists`.

A refusal SHALL come back in the tool result so the coach explains it, and no action is stored.

The preview SHALL show:

- the payment in words ("850,00 € every month, day 1"; for changes, before → after);
- the category's normal and "to be on time" monthly amounts before → after;
- this month's assignment before → after;
- To be assigned before → after;
- the next due month and the "estimated" mark when set.

Undo SHALL be allowed while the payment still holds what the action left (for removal: while no payment with the same fields was added back). It deletes a created payment, restores a changed one, or recreates a removed one, through the same shared operation.

#### Scenario: Rent from a sentence

- **WHEN** the user writes "el alquiler son 850 € al mes, el día 1" and "Alquiler" exists without payments
- **THEN** the preview shows "850,00 € every month, day 1", Alquiler's monthly amount going from 0,00 € to 850,00 €, and To be assigned going down by the same amount for October, and nothing is saved until Confirm

#### Scenario: An annual payment with something saved

- **WHEN** the user writes "el seguro del coche son 600 en febrero" for a category with 200,00 € carried in, in October 2026
- **THEN** the preview shows an annual payment in February, a normal amount of 50,00 € and "to be on time" 80,00 €, with February 2027 as the next due month

#### Scenario: An approximate amount

- **WHEN** the user writes "el agua unos 120 cada 3 meses desde noviembre"
- **THEN** the proposed payment is `every_n` 3 from November, 120,00 €, marked estimated

#### Scenario: A debt's installment

- **WHEN** the user asks to change the payment of a loan that's managed from What you owe
- **THEN** the tool returns `managed_by_debt`, no action is stored, and the coach points to What you owe

#### Scenario: Payment for a new category

- **WHEN** the user writes "el gimnasio son 35 al mes" and no category is similar
- **THEN** the reply shows the category choice; after "Create 'Gimnasio'" in a chosen group, the payment preview for it appears, waiting for Confirm

#### Scenario: Changing and undoing

- **WHEN** the user confirms "el alquiler sube a 900" and then taps Undo right away
- **THEN** the payment is back to 850,00 € and October's assignment for Alquiler is back to 850,00 €
