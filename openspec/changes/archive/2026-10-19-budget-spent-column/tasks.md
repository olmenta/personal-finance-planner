## 1. Row layout

- [x] 1.1 `globals.css`: row-grid classes next to `assign-edit-desktop`/`assign-edit-mobile` (three fixed-width right-aligned cells from 1024px; a labeled three-cell second line below) (D1, D2).
- [x] 1.2 `AssignRow`: Assigned (inline input, numpad button or payment-driven text, unchanged behavior), Spent (`spent_cents`, neutral; "Paid" for card payment categories) and the Available pill as the three cells; `data-testid` `spent-<name>` on the Spent cell (D1, D3).
- [x] 1.3 `AssignRow`: carry-over line under Assigned when `rollover_cents ≠ 0` ("+X € from last month"); for card payment categories "+X € set aside" (D4).
- [x] 1.4 `AssignRow`: the subtitle keeps only the payment notes; "Spent X" and "set aside … from card purchases" leave it (D5).
- [x] 1.5 Mobile: labels above each value on the second line; the assigned cell still opens the numpad sheet (D2).
- [x] 1.6 Mobile hero (D7): below 1024px the to-be-assigned bar hides its "Confirm remaining" action (the suggestions capsule offers the same one), so the amount and its explanation get the full width.
- [x] 1.7 Coach capsule on narrow screens (D7): the message wraps (two lines at most) and the CTA moves under it instead of cutting the message to "8 su…"; the all-drafts message names the real months instead of the hard-coded "May's plan fits June".

## 2. Group headers

- [x] 2.1 `AssignGroups`: a header row per group with "Assigned · Spent · Available" labels (`.ol-eyebrow`) and the group's three subtotals aligned with the cells, replacing today's "Assigned … · Available …" text (D1).

## 3. Docs

- [x] 3.1 `docs/user-guide.md`: "Spent" in the plain-word glossary; the Budget section describes the three amounts and the carry-over line. Check `docs/debt-guide.md` for the card payment row ("Paid").

## 4. Verification

- [x] 4.1 e2e: a budget spec checks the column labels, a category's Spent value, the carry-over line and the "Paid" label on a card payment category, on desktop and on a mobile viewport; update locators that read the old subtitle.
- [x] 4.2 Type check and lint green in `webapp/`; `volta run npm run e2e` green.
