# home Specification

## Purpose
TBD - created by archiving change redesign-home-navigation. Update Purpose after archive.
## Requirements
### Requirement: Home API

The API SHALL expose `GET /home`, which composes existing services for the current month (Europe/Madrid) without computing any amount of its own. The response SHALL contain:

- `month` and `generated_at`;
- `summary`, mapped from the month overview:
  - `accounts_cents = M`;
  - `covered_cents = T`;
  - `left_to_spend_cents = L`, which is the overview's `left_to_spend.total_cents − overspent_cents`;
  - `saved_cents = F`;
  - `unassigned_cents = U` (To Be Assigned);
  - plus `paid_cents`, `card_payments_cents`, `still_to_pay_cents` (the full pending obligation) and `short_cents` (its uncovered part);
- `status` and `reasons`;
- `data`, the data status;
- `future`, the Future status;
- `priority`: the most urgent visible coach proposal, or null;
- `groups`: the remaining visible proposals grouped by cause;
- `snapshot_version`: a hash of the summary, the statuses and the proposal fingerprints and revisions.

The response SHALL satisfy `M = T + L + F + U` exactly. Already paid and card payments are flows and SHALL NOT be part of that identity.

#### Scenario: The identity holds

- **WHEN** any user requests `GET /home`
- **THEN** `accounts_cents` equals `covered_cents + left_to_spend_cents + saved_cents + unassigned_cents`

#### Scenario: Screenshot reconciliation

- **WHEN** the overview reports 55,00 € covered, 577,96 € saved, 4.406,12 € unassigned, a net spending balance of −1.004,53 € and 4.034,55 € in accounts
- **THEN** the summary maps them to T, F, U, L and M, and they reconcile exactly

#### Scenario: Same data, same version

- **WHEN** Home is requested twice with no change in between
- **THEN** both responses carry the same `snapshot_version`, and any money write or proposal change produces a different one

### Requirement: Month status and its reasons

`status` SHALL be:

- `not_set_up` when the user hasn't set up a budget yet: no categories and no transactions (a new user, before the onboarding or the starter template);
- otherwise `no_accounts` when the user has no active account;
- otherwise `needs_organizing` when at least one reason applies;
- otherwise `organized`.

Reasons, each with its amount in cents:

| Code | When |
|---|---|
| `over_assigned` | To Be Assigned is below zero |
| `overspent_categories` | Categories are overspent (cash); the reason lists each category and its amount |
| `unbudgeted_card_spending` | Card spending exceeded its category |
| `uncovered_payments` | This month's pending payments are short |

In `not_set_up` there's nothing to analyze: the response SHALL carry no reasons, no priority and no suggestion groups, and Home SHALL show no amounts, only the invitation to the setup chat.

When the status isn't `organized`, Home SHALL NOT present "Left to spend" as money you can spend. It shows the status and keeps the exact figure in the breakdown.

#### Scenario: Unassigned money and overspent categories at once

- **WHEN** To Be Assigned is 4.406,12 € and day-to-day categories are 1.004,53 € overspent in total
- **THEN** the status is `needs_organizing` with an `overspent_categories` reason of 100453 listing the categories, and the response never treats the negative figure as an overdrawn bank account

#### Scenario: Organized month

- **WHEN** To Be Assigned is zero or positive, nothing is overspent and every pending payment is covered
- **THEN** the status is `organized` and Home shows "Left to spend" with its amount

#### Scenario: No accounts

- **WHEN** the user has no active accounts
- **THEN** the status is `no_accounts`, and Home invites adding an account and its balance without showing amounts

#### Scenario: A new user before setup

- **WHEN** a user who has just signed in for the first time, with only the empty cash account, opens Home
- **THEN** the status is `not_set_up`, there are no reasons or suggestions, and Home invites the setup chat instead of saying "I've updated your month"

#### Scenario: Setup done another way

- **WHEN** that user applies the starter template, or records money without the onboarding
- **THEN** the status is no longer `not_set_up`

### Requirement: Data status

`data` SHALL report:

- `last_transaction_date`: the newest confirmed transaction, or null;
- `uncategorized_count`: confirmed outflows without a category this month;
- `pending_import`: whether an import batch is waiting for review;
- `income_known`: whether there are income schedules;
- `limited`: true when there are uncategorized outflows, a pending import, or no transaction in the last 14 days.

When `limited` is true, Home SHALL say what limits the picture, with a link to fix it.

#### Scenario: An import is waiting

- **WHEN** a statement import is staged and not confirmed
- **THEN** `data.pending_import` is true, `data.limited` is true, and Home links to the review

#### Scenario: Stale data

- **WHEN** the newest confirmed transaction is 20 days old
- **THEN** `data.limited` is true, and Home shows the last transaction date and suggests recording or importing recent spending

### Requirement: Future status

`future.status` SHALL be:

- `unknown` when there are no income schedules;
- `needs_attention` when any later month of the projection has an uncovered payment or set-asides funded below what's wanted, reporting the first such month and its amounts;
- `on_track` otherwise.

The copy SHALL always qualify the status as depending on the current plan and expected income.

#### Scenario: Coverage unknown

- **WHEN** the user has no income schedules
- **THEN** `future.status` is `unknown`, and Home invites adding expected income instead of claiming coverage

#### Scenario: Set-asides behind with no short payment

- **WHEN** every later payment is covered but set-asides are funded below what's wanted in some month
- **THEN** `future.status` is `needs_attention`, not `on_track`

### Requirement: Grouped recommendations and priority action

The most urgent visible coach proposal SHALL be the `priority`. The remaining visible proposals SHALL be grouped by cause, and each group carries a title and its proposals:

- `late`: late income and late debt payments;
- `coming_up`: short months;
- `adjustments`: overspending and underspending;
- `unassigned`: money with no job.

Groups SHALL be ordered by their most urgent proposal. A proposal SHALL appear only once, so the priority isn't repeated inside a group. Home SHALL show up to three groups, with the rest on demand.

#### Scenario: No repetition

- **WHEN** the most urgent proposal is an overspending of "Alquiler" and two more adjustments exist
- **THEN** "Alquiler" appears only as the priority action, and the "Budget adjustments" group shows the other two

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

