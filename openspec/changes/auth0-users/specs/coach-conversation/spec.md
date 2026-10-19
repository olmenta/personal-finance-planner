## MODIFIED Requirements

### Requirement: Conversation screen

Home SHALL render the conversation:

1. **Header:** "Home", the subtitle "Your conversation with Olmenta", and a History button.
2. **Date separators** between days.
3. **The unstored snapshot message** at the bottom of the history on each visit. It is a coach bubble with:
   - the month in one or two sentences (money in accounts, what's reserved, payments covered or not, the Future status);
   - "View how it's split", expanding the breakdown;
   - the priority action;
   - a link to the other suggestions.

   Before setup (home status `not_set_up`), the snapshot SHALL instead invite the setup chat ("Let's set up your budget", "Start the setup chat" → `/onboarding`), with no amounts, breakdown or suggestions, and the onboarding nudge SHALL NOT repeat it. The coach SHALL NOT analyze the month in that state; it answers briefly and points to the setup chat.
4. **Stored messages:** user bubbles on the right with their time; coach bubbles on the left with their widgets.
5. **The composer:** "+" opening the add-transaction form, the field "Ask or record an expense…", the send button, and the note "Your history is kept".

The draft and the scroll position SHALL survive leaving and returning to Home. While the coach is answering, Home SHALL show progress and keep the forms reachable. Statuses SHALL be stated in text, not only color.

#### Scenario: Asking from Home

- **WHEN** the user types a question and sends it
- **THEN** their bubble appears on the right, a progress line shows while the coach answers, and the reply appears with its widgets

#### Scenario: Draft kept

- **WHEN** the user types half a message, opens Budget and comes back
- **THEN** the draft is still in the field

#### Scenario: Home before setup

- **WHEN** a new user opens Home
- **THEN** the snapshot invites the setup chat, shows no amounts, and "Start the setup chat" opens `/onboarding`
