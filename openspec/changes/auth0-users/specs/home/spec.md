## MODIFIED Requirements

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
