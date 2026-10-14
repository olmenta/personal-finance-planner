## MODIFIED Requirements

### Requirement: What you owe screen

The webapp SHALL provide a "What you owe" screen at `/debts`, reached from a "What you owe" card on Accounts (total owed and debt-free month), with Accounts highlighted in the navigation while it is open. It SHALL show:

- the total owed, and the debt-free month ("Debt-free in June 2028 if you keep this plan") or a plain explanation when there is none;
- the debts in order, each with its name, amount owed, its required payment and end, and its rate in plain words ("1,5 % a month", "no interest", "rate unknown");
- for the first debt, one sentence explaining why it goes first and, when a rate is known, "~X €/month just for owing it";
- the monthly extra with an edit control, and the cushion note when it applies;
- an always-visible "Work on my debts" button in the header and on every debt row, opening the plan editor;
- an empty state that invites adding a first debt, never apologizing.

The copy SHALL avoid finance jargon: no TAE, APR, amortization, snowball or avalanche.

#### Scenario: Reading the plan

- **WHEN** the user has a card, a loan and a personal debt
- **THEN** the screen shows the total, the debt-free month, the card first with its reason and interest sentence, and a "Work on my debts" button

#### Scenario: Paid off

- **WHEN** a debt's `owed_cents` reaches zero
- **THEN** it shows as paid off with a short celebration line and offers to remove its plan
