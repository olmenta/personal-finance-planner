## MODIFIED Requirements

### Requirement: Coach feed

Home SHALL show the coach feed as grouped recommendations (see home): there is no Coach rail and no `/coach` page, and no text input until the conversation change. Each group expands to its proposal cards, each with:

- the title and body;
- the action button ("Raise it", "Lower it", "Add it", "It's already here", "See my plan", "See the month", "Give it a job");
- "Not now".

Home shows up to three groups; "See more" SHALL reveal the rest. Choosing a `raise` that has `sources` SHALL show them so the user picks where the money comes from. An empty feed SHALL say there are no suggestions right now; it SHALL NOT claim the plan is on track, because a dismissed warning, missing income or an unfunded set-aside can all leave the feed empty. The sparkle icon SHALL mark the feed as the coach.

#### Scenario: Grouped on Home

- **WHEN** there are proposals of four different causes
- **THEN** Home shows the most urgent as the priority action, three groups with their counts, and "See more" for the last group

#### Scenario: Raise with not enough to assign

- **WHEN** the user taps "Raise it" on a proposal that carries sources
- **THEN** the card lists those categories, and picking "Ocio" accepts the raise moving the money from it

#### Scenario: Nothing to say

- **WHEN** there are no visible proposals
- **THEN** the feed says there are no suggestions right now, without saying the plan is on track

### Requirement: Dashboard coach capsule

Home SHALL show the most urgent proposal as its priority action, above the recommendation groups, with its action and "Not now". It SHALL appear only once (not repeated in a group). When there are no proposals, no priority action is shown.

#### Scenario: Late income first

- **WHEN** on 31 October "Nómina" is late and "Restaurantes" has an overspending proposal
- **THEN** the priority action shows the late "Nómina" with "Add it" and "It's already here"

#### Scenario: Not now on Home

- **WHEN** the user taps "Not now" on the priority action
- **THEN** the next proposal takes its place, and the dismissed one stays hidden for a week
