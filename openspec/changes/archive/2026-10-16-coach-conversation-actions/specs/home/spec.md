## MODIFIED Requirements

### Requirement: Home screen

Home SHALL render as the conversation (see coach-conversation), in one column on every screen size. The snapshot is shown as the unstored coach message after the stored history; its parts are:

1. **The month in sentences:** money in accounts and how much of it is already set aside for payments and savings.
2. **"View how it's split"**, expanding the month widget with the exact breakdown open:
   - Paid;
   - Still to pay, with its covered and short amounts;
   - Left to spend, or "Needs organizing" with its reasons;
   - Saved;
   - Unassigned;
   - the breakdown listing M = T + L + F + U.
3. **A deterministic coach line** stating the most important fact: the status reason (with the reasons listed when the month needs organizing), or that the month is organized. It's never a greeting added on every visit.
4. **The payments and Future sentence:** whether this month's payments are covered, the qualified Future status, and a link to Future (or to add income).
5. **The priority action**, with its buttons and "Not now".
6. **"N more suggestions"**, revealing up to three recommendation groups, collapsed to a title and count, expanding to their cards; "See more" for the rest.
7. **The data line:** the month, "Updated" with the time, and "Review data" when the data is limited.

The composer ("Ask or record an expense…") and the History button SHALL always be present. Home SHALL NOT show the category list, the weekly chart or the transaction list. It SHALL work without the AI service. States SHALL be expressed in text, not only color. No humor SHALL be used for shortfalls.

#### Scenario: Needs organizing at a glance

- **WHEN** the status is `needs_organizing` because two categories are overspent
- **THEN** the coach line says two categories need money before the amount to spend is reliable and lists both, and "View how it's split" shows "Needs organizing" in the month widget with a breakdown that still reconciles

#### Scenario: Recommendations collapsed

- **WHEN** there are four groups of proposals besides the priority action
- **THEN** "N more suggestions" shows three group headers with their counts, and "See more" reveals the fourth

#### Scenario: The snapshot as a coach message

- **WHEN** the user opens Home
- **THEN** the last bubble is the coach's month summary with "View how it's split", it is not stored as a message, and the composer is below it
