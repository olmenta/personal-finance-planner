## Context

[AssignRow](../../../webapp/src/components/budget/AssignRow.tsx) renders each category in one flex line:

- the icon chip;
- the name, with a muted subtitle ("Spent 45,00 € · normal … · to be on time …");
- the assigned amount: an inline input on desktop, a button that opens the numpad sheet on mobile, or plain text for categories driven by payments;
- the available pill;
- a chevron that expands the formula breakdown, "rollover + assigned − spent = available".

[AssignGroups](../../../webapp/src/components/budget/AssignGroups.tsx) puts "Assigned X · Available Y" in each group header, on desktop only.

Every number already comes from `GET /budget/{month}`. Available is `rollover + assigned − spent` (plus the set-aside amount for card payment categories), computed by `availableCents`.

## Goals / Non-Goals

**Goals:**

- Each row reads as "Assigned · Spent · Available", labeled, in that order, on desktop and on mobile.
- The math is visible without expanding the row, including the carry-over.
- No new API fields, and no change to how assigning works (inline input on desktop, numpad on mobile).

**Non-Goals:**

- Changing the formula breakdown, quick-fill, cover or move-money actions.
- A Report mode redesign.
- Showing spending per transaction. That stays in Transactions.

## Decisions

### D1. Three columns on desktop, with headers per group

From 1024px up, the right side of each row is a three-column grid of fixed-width cells, right-aligned with tabular numerals: Assigned, Spent and Available, followed by the chevron.

- **Headers:** each group panel starts with a header row of tiny uppercase labels (the `.ol-eyebrow` treatment, the one place uppercase is allowed): "Assigned", "Spent", "Available", aligned with the cells.
- **Subtotals:** the group header's subtotals move into the same columns: Σ assigned, Σ spent, Σ available. Σ available turns red when negative, as today.
- **Why per group, not once per screen:** groups are separate panels and the list is long. Headers inside each panel stay next to the numbers they label.

### D2. Mobile: a labeled second line

Below 1024px, row width doesn't allow three columns next to the name.

- **The layout:** the first line keeps the chip, the name and the chevron. A second line, indented under the name, shows three equal cells, each with a tiny label above its value: Assigned (the button that opens the numpad sheet), Spent, and Available (the pill).
- **The breakpoint:** the same 1024px boundary that already switches the inline input and the numpad (`assign-edit-desktop` / `assign-edit-mobile`). The new classes live next to those in `globals.css`, not in a one-off media query.

### D3. How Spent looks

- **The value:** `spent_cents` as a plain amount, "45,00 €". It's neutral text, never red: spending a budget is normal, and red is reserved for overspending (the negative available pill).
- **A refund-heavy month:** when refunds exceed purchases, `spent_cents` is negative and shows as "−5,00 €".
- **Card payment categories:** the label reads **Paid**, matching today's subtitle and breakdown, because the value is the month's payments to the card.

### D4. Carry-over under Assigned

When `rollover_cents ≠ 0`, a muted line under the assigned amount reads "+32,00 € from last month". With it, the row adds up on screen: assigned plus carry-over, minus spent, equals available.

- **Card payment categories** also show "+X € set aside", the money funded by card purchases. Today that sits in the subtitle; this way all the inputs to Available are in the Assigned column.
- **Overspending reset at the month start** (`rollover_reset_cents`) stays in the expanded breakdown, as today.

### D5. The subtitle loses "Spent"

The subtitle under the name keeps only the payment notes ("normal X · to be on time Y"). "Spent X" moves to its column, and "set aside … from card purchases" moves under Assigned (D4). A row with no notes has no subtitle, so it's one line shorter.

### D6. The progress bar stays

The bar under the row (spent against assigned plus carry-over) stays as it is, as the visual complement of the numbers.

### D7. The mobile to-be-assigned bar

At 390px, the sticky hero squeezed its text into a narrow column: the amount was cut ("3.58…") and the bar covered half the screen. The cause was the "Confirm remaining (N)" button next to it. The suggestions capsule right under the hero shows the same action under the same condition, so below 1024px the hero hides its action (`.tba-hero-action`). Desktop is unchanged.

The capsule had the same problem: at 390px its "Confirm remaining (8)" CTA left room for "8 su…".

- **`CoachCapsule` wraps:** the message can take two lines, and when the message and the CTA don't fit on one line, the CTA moves under the message. It stays a pill on one line (radius 27 at 54px tall) and becomes a rounded card when wrapped. Every capsule benefits, including the onboarding nudge on Home.
- **The real months:** the all-drafts message used a hard-coded "May's plan fits June", a mock leftover. It now names last month and this month from the viewed month.

## Risks / Trade-offs

- **[Narrow tablets around 1024px squeeze the name]** → The name keeps its ellipsis. The three cells have fixed widths sized for "−1.234,56 €" at the row's font size, and the name takes the rest.
- **[Mobile rows get taller]** → The second line replaces the subtitle line that most rows already have, so most rows end up about the same height.
- **[e2e locators that read the subtitle's "Spent X" text]** → Update them to read the Spent cell (`data-testid="spent-<category>"`).
