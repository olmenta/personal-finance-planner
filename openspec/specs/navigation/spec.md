# navigation Specification

## Purpose
TBD - created by archiving change redesign-home-navigation. Update Purpose after archive.
## Requirements
### Requirement: Five destinations

The app SHALL offer five destinations: Home (`/`), Budget (`/budgets`), Transactions (`/transactions`), Future (`/future`) and Accounts (`/accounts`).

- **Desktop sidebar:** it SHALL list them in that order, with Settings at the bottom.
- **Mobile bottom navigation:** it SHALL show the five labeled destinations around the centered add-transaction button.
- **Settings on mobile:** it SHALL be reachable from the top bar.
- **Active destination:** Accounts SHALL be highlighted on `/debts`; Budget on category management reached from it.
- **Goals and Coach** SHALL NOT be destinations.

#### Scenario: Desktop sidebar

- **WHEN** the app is opened on a wide screen
- **THEN** the sidebar shows Home, Budget, Transactions, Future and Accounts, then Settings

#### Scenario: Mobile navigation

- **WHEN** the app is opened on a phone
- **THEN** the bottom bar shows the five labeled destinations and the add-transaction button, and the top bar links to Settings

### Requirement: Redirects for moved screens

`/upcoming` SHALL redirect to `/future`, keeping its `month` query parameter. `/coach` SHALL redirect to Home.

#### Scenario: Old link to a month

- **WHEN** the user opens `/upcoming?month=2027-03`
- **THEN** they land on `/future?month=2027-03` with March expanded

