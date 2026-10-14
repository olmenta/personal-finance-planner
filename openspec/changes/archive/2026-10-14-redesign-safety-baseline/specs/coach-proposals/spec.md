## ADDED Requirements

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

## MODIFIED Requirements

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
