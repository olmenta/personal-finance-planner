# coach-proposals Specification

## Purpose

Rule-based coach proposals from data the app already computes: the proposal kinds and their thresholds, the proposals API (list, dismiss for a week, accept a raise or lower bound to the reviewed revision), urgency order, server-side state without amounts, valid funding sources, the coach feed in the rail and on /coach, and the dashboard coach capsule.

## Requirements

### Requirement: Proposal kinds and their rules

The backend SHALL detect these proposal kinds for the current month (Europe/Madrid). Each proposal SHALL have a stable `fingerprint` (kind + subject + month), a `kind`, an `urgency` rank, a plain-language `title` and `body` with exact amounts, and one primary `action`.

| kind | detected when | subject | action |
|---|---|---|---|
| `late_income` | an income occurrence of the current month is `late` (income-schedules) | the income schedule | `add_income` (amount, payer) or `link_income` |
| `late_debt_payment` | a `to_pay` entry of the current month reports `late` (month overview) | the debt's category | `open` `/debts` |
| `short_months` | the projection from the current month has at least one later month with an uncovered payment; all such months are grouped into one proposal | the earliest short month | `open` `/upcoming` at that month |
| `overspending` | a day-to-day (flexible) category ended overspent (available below zero) in at least 2 of the last 3 closed months, and the average actual spending of those 3 months, rounded up to the next 5 €, exceeds this month's assignment by at least 10,00 € | the category | `raise` to that amount |
| `unassigned` | the current month's To Be Assigned is at least 10,00 € | — | `open` `/budgets` |
| `underspending` | a day-to-day category had money left over (spent below assigned) in all of the last 3 closed months, and this month's assignment exceeds the average actual spending, rounded up to the next 5 €, by at least 10,00 € | the category | `lower` to that amount |

Categories with payments, savings categories and card payment categories SHALL never get `overspending` or `underspending` proposals. A category needs at least 3 closed months of history for either.

#### Scenario: Restaurants keeps going over

- **WHEN** "Restaurantes" was assigned 200,00 € and spent 240,00 €, 190,00 € and 250,00 € in July, August and September (overspent in July and September), and October's assignment is 200,00 €
- **THEN** an `overspending` proposal suggests raising it to 230,00 € (the 226,67 € average rounded up to the next 5 €)

#### Scenario: Fuel always has money left

- **WHEN** "Gasolina" was assigned 120,00 € and spent 55,00 €, 62,00 € and 58,00 € in the last 3 closed months
- **THEN** an `underspending` proposal suggests lowering it to 60,00 €

#### Scenario: Small differences are ignored

- **WHEN** a category's suggested amount is within 10,00 € of this month's assignment
- **THEN** no raise or lower proposal is produced for it

#### Scenario: Short months grouped

- **WHEN** the projection shows uncovered payments in March and June
- **THEN** one `short_months` proposal says March and June won't be fully covered and opens Upcoming payments at March

#### Scenario: Money with no job

- **WHEN** October's To Be Assigned is 210,00 €
- **THEN** an `unassigned` proposal says "You have 210,00 € with no job yet" and opens the budget

### Requirement: Proposals API and urgency order

The API SHALL expose `GET /coach/proposals`, returning the visible proposals ordered by urgency, then by amount (largest first): `late_income`, `late_debt_payment`, `short_months`, `overspending`, `unassigned`, `underspending`. The response SHALL also return `total`.

Each `raise` or `lower` proposal SHALL carry the category, its current assignment, the suggested amount, and the difference. A `raise` that needs more than this month's To Be Assigned SHALL also carry `sources`: up to 3 day-to-day categories, by available descending, whose available covers the difference.

#### Scenario: Ordered by urgency

- **WHEN** the user has a late income, an overspending proposal and money with no job
- **THEN** the list is the late income, then the overspending, then the money with no job

### Requirement: Dismissing and accepting

`POST /coach/proposals/{fingerprint}/dismiss` SHALL hide that proposal for 7 days. After that, it reappears if its condition still holds.

`POST /coach/proposals/{fingerprint}/accept` SHALL apply a `raise` or `lower`:

- It sets this month's assignment of the category to the suggested amount.
- For a `raise` with `from_category_id`, it moves the difference from that category instead of taking it from To Be Assigned.
- It records the proposal as accepted, so it doesn't reappear for the same fingerprint.

A `raise` without a source that needs more than To Be Assigned SHALL return 409 `not_enough_to_assign`. Accepting a kind without a one-tap action SHALL return 409 `not_acceptable`. An unknown fingerprint SHALL return 404 `proposal_not_found`.

Proposal state SHALL store only the fingerprint, the state and the time. It SHALL hold no amounts, names or other financial data.

#### Scenario: Not now hides for a week

- **WHEN** the user dismisses the "Restaurantes" overspending proposal on 14 October
- **THEN** it's absent from the list until 21 October, and reappears then if the condition still holds

#### Scenario: Accepting a raise

- **WHEN** the user accepts raising "Restaurantes" from 200,00 € to 230,00 € with 210,00 € to assign
- **THEN** October's assignment is 230,00 €, To Be Assigned drops to 180,00 €, and the proposal is gone

#### Scenario: Raise needs a source

- **WHEN** the raise needs 30,00 € but To Be Assigned is 10,00 €
- **THEN** accepting without a source returns 409 `not_enough_to_assign`, and accepting with `from_category_id` of "Ocio" moves 30,00 € from "Ocio" to "Restaurantes"

#### Scenario: Lower frees money

- **WHEN** the user accepts lowering "Gasolina" from 120,00 € to 60,00 €
- **THEN** October's assignment is 60,00 € and To Be Assigned rises by 60,00 €

### Requirement: Coach feed

The Coach rail (≥1440px) and the `/coach` page SHALL show the coach feed instead of the scripted conversation. The text input SHALL be removed. The feed SHALL show the first 3 proposals as cards, each with:

- the title and body;
- the action button ("Raise it", "Lower it", "Add it", "It's already here", "See my plan", "See the month", "Give it a job");
- "Not now".

When there are more, "See more (N)" SHALL reveal the rest. Choosing a `raise` that has `sources` SHALL show them so the user picks where the money comes from. An empty feed SHALL say there are no suggestions right now; it SHALL NOT claim the plan is on track, because a dismissed warning, missing income or an unfunded set-aside can all leave the feed empty. The sparkle icon SHALL mark the feed as the coach.

#### Scenario: Three visible, more on demand

- **WHEN** there are 5 proposals
- **THEN** the feed shows 3 cards and "See more (2)", and tapping it shows all 5

#### Scenario: Raise with not enough to assign

- **WHEN** the user taps "Raise it" on a proposal that carries sources
- **THEN** the card lists those categories, and picking "Ocio" accepts the raise moving the money from it

#### Scenario: Nothing to say

- **WHEN** there are no visible proposals
- **THEN** the feed says there are no suggestions right now, without saying the plan is on track

### Requirement: Dashboard coach capsule

The dashboard SHALL show the most urgent proposal as one coach capsule above "Este mes", with its action and "Not now". It SHALL replace the separate late-income and late-debt capsules and the static coach capsule. When there are no proposals, no capsule is shown.

#### Scenario: Late income first

- **WHEN** on 31 October "Nómina" is late and "Restaurantes" has an overspending proposal
- **THEN** the dashboard capsule shows the late "Nómina" with "Add it" and "It's already here"

#### Scenario: Not now on the dashboard

- **WHEN** the user taps "Not now" on the capsule
- **THEN** the next proposal takes its place, and the dismissed one stays hidden for a week

### Requirement: Accepting exactly the reviewed change

Every `raise` and `lower` proposal SHALL carry a `revision`: a hash of its fingerprint, category, current amount, suggested amount, difference and source ids. `POST /coach/proposals/{fingerprint}/accept` SHALL require that `revision`. When the recomputed proposal no longer has the same revision (spending or assignments changed since it was shown), the API SHALL return 409 `proposal_changed` with the current proposal and apply nothing. Accepting a revision that was already accepted SHALL return success without applying it again. The accepted revision SHALL be stored with the proposal state; it holds no amounts.

#### Scenario: The proposal changed before acceptance

- **WHEN** a raise to 230,00 € was shown and a later expense makes the recomputed suggestion 330,00 €
- **THEN** accepting with the shown revision returns 409 `proposal_changed` with the 330,00 € proposal, and the assignment is unchanged

#### Scenario: Accepting twice applies once

- **WHEN** the user accepts a raise and the request is retried with the same revision
- **THEN** the second call succeeds and the assignment is raised only once

### Requirement: Valid funding sources

A `raise` funded from another category SHALL follow the budget's move rules: the source SHALL differ from the target (422 `same_category`), SHALL be a day-to-day category that is not archived and not a card payment, scheduled or savings category, and its available SHALL cover the difference (409 `not_enough_in_source`). Forms and the coach SHALL use the same validation. A rejected request SHALL change nothing.

#### Scenario: A category can't fund itself

- **WHEN** a client accepts a raise of "Restaurantes" with `from_category_id` set to "Restaurantes"
- **THEN** the API returns 422 `same_category`, and the assignments and To Be Assigned are unchanged

#### Scenario: A savings category is not a free source

- **WHEN** a client accepts a raise with a savings category as the source
- **THEN** the API returns 409 `not_enough_in_source`, and nothing changes
