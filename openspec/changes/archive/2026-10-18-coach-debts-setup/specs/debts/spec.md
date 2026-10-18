## MODIFIED Requirements

### Requirement: What you owe screen

The webapp SHALL provide a "What you owe" screen at `/debts`, reached from a "What you owe" card on Accounts (total owed and debt-free month), with Accounts highlighted in the navigation while it is open. It SHALL show:

- the total owed, and the debt-free month ("Debt-free in June 2028 if you keep this plan") or a plain explanation when there is none;
- the debts in order, each with its name, amount owed, its required payment and end, and its rate in plain words ("1,5 % a month", "no interest", "rate unknown");
- for the first debt, one sentence explaining why it goes first and, when a rate is known, "~X €/month just for owing it";
- the monthly extra with an edit control, and the cushion note when it applies;
- an always-visible "Work on my debts" button in the header and on every debt row, opening the plan editor;
- "Talk it through with your coach", which opens Home with the draft "Quiero ordenar mis deudas" in the composer, ready to send;
- an empty state that invites adding a first debt, never apologizing.

The copy SHALL avoid finance jargon: no TAE, APR, amortization, snowball or avalanche.

#### Scenario: Reading the plan

- **WHEN** the user has a card, a loan and a personal debt
- **THEN** the screen shows the total, the debt-free month, the card first with its reason and interest sentence, and a "Work on my debts" button

#### Scenario: Paid off

- **WHEN** a debt's `owed_cents` reaches zero
- **THEN** it shows as paid off with a short celebration line and offers to remove its plan

#### Scenario: From the plan to the conversation

- **WHEN** the user taps "Talk it through with your coach"
- **THEN** Home opens with "Quiero ordenar mis deudas" in the composer, not yet sent

## ADDED Requirements

### Requirement: One shared debt operation

Creating, updating and deleting a debt, setting the extra and converting a credit account to a loan SHALL go through one backend operation used by the debts API, the coach and the dev MCP server (through the API). It SHALL validate the input from plain data (422 `invalid_debt`, or `outside_planning_horizon` for a due month beyond the horizon), apply the existing debt rules, and raise the existing codes (`debt_exists`, 404s). The API's responses and error codes SHALL stay as they are.

#### Scenario: Same rules from the chat and the editor

- **WHEN** the coach confirms a card debt with `target_month = January` for a −634,62 € card in October, without a rate
- **THEN** the plan is 158,66 € a month, exactly as if it had been created from the plan editor

#### Scenario: Same refusal

- **WHEN** the coach proposes a second debt for a card that already has one
- **THEN** it's refused with `debt_exists`, as the API does
