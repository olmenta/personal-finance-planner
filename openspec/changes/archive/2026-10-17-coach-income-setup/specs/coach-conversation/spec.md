## ADDED Requirements

### Requirement: Setting up expected income from the conversation

The coach SHALL be able to propose expected income (income schedules) with these tools, each storing an action with a dry-run preview and the usual revision, confirm, idempotency and undo lifecycle:

- `propose_income(name, amount, pattern, months?, month?, every_n?, start_month?, once_month?, count?, day?, estimated?, payer?)` (kind `income`);
- `propose_income_change(income, …only the fields that change)` (kind `income_update`): the income is named by its name or its payer; ambiguous names are an error listing the candidates;
- `propose_income_removal(income)` (kind `income_delete`).

The patterns are the income-schedule ones (`no_date` is not allowed). Every write SHALL go through the shared income operation (income-schedules), so the editor's rules apply (`invalid_schedule`, `outside_planning_horizon`). A refusal SHALL come back in the tool result so the coach explains it, and no action is stored.

The preview SHALL show:

- the income in words, with its payer (for changes, before → after);
- this month's expected income before → after;
- the next 12 months' expected income before → after;
- the year's coverage before → after (the plan summary's gap, or "unknown" without income);
- the note that To be assigned is unchanged until money arrives.

The preview and the recorded "before" use the income as it is at that moment. Undo SHALL be allowed while the income still holds what the action left. It deletes a created income, restores a changed one, or recreates a removed one (while no identical income was added back), through the same operation.

#### Scenario: A salary from a sentence

- **WHEN** the user writes "cobro 2.100 € el día 28 de Acme" and has no expected income
- **THEN** the preview shows "2.100,00 € every month, day 28, from Acme", this month's expected income going from 0,00 € to 2.100,00 €, and the year's coverage going from unknown to its gap or "covered", with To be assigned unchanged, and nothing is saved until Confirm

#### Scenario: Fourteen pagas

- **WHEN** the user writes "cobro 1.800 en 14 pagas, con las extras en junio y diciembre"
- **THEN** the coach proposes two incomes: 1.800,00 € every month, and 1.800,00 € in June and December

#### Scenario: Approximate income

- **WHEN** the user writes "me pagan unos 400 al mes de clases"
- **THEN** the proposed income is monthly, 400,00 €, marked estimated

#### Scenario: Undo a change

- **WHEN** the user confirms "mi sueldo sube a 2.200" and then taps Undo
- **THEN** the income is back to 2.100,00 €

### Requirement: Linking income that arrived to what was expected

`propose_income_link(transaction, income)` (kind `income_link`) SHALL propose linking an unplanned inflow of a month to an expected income with an occurrence in that month, through the shared linking rule (income-schedules). The transaction is named by its `ref` from `get_income` or `search_transactions`. The preview SHALL show the occurrence's status and received amount before → after, and whether the inflow leaves "unplanned". Undo SHALL restore the previous payers while both still hold the values the link set.

#### Scenario: The salary without its payer

- **WHEN** a 2.080,00 € inflow without payer is unplanned, the "Nómina" occurrence from Acme is late, and the user says "ese ingreso de 2.080 es la nómina"
- **THEN** the preview shows the occurrence going from late to received with 2.080,00 €; after Confirm the inflow has the payer Acme and is no longer unplanned
