## Why

On Budget, each category row shows two numbers without labels: the assigned amount and the available pill. What was spent appears only as a small grey line under the name ("Spent 45,00 €"). People new to budgeting can't tell which number is which, or why the available amount is what it is. Showing the three numbers side by side and labeled (what you gave the category, what you spent, what's left) makes each one, and the math between them, readable at a glance.

## What Changes

- **Every category row shows three labeled amounts, in order:**
  1. **Assigned:** editable, as today.
  2. **Spent:** the month's spending in the category, which is today's `spent_cents`. Card payment categories label it **Paid**.
  3. **Available:** the existing pill, colored by sign.
- **Desktop:** the labels sit once at the top of each group, as column headers aligned with the amounts. The group's subtotals for Assigned, Spent and Available sit in the same columns, replacing today's "Assigned … · Available …" text.
- **Mobile:** the three labeled amounts form a second line under the category name. The assigned amount still opens the numpad sheet.
- **Carry-over:** when a category carries money from last month, a small line under Assigned shows "+32,00 € from last month", so Assigned + carry-over − Spent visibly equals Available.
- **The subtitle under the name no longer repeats "Spent X".** It keeps the payment notes ("normal … · to be on time …", "set aside … from card purchases").
- **The user guide's glossary gains "Spent".**
- **The mobile to-be-assigned bar gets its full width back.** It hides its "Confirm remaining" button, which the suggestions capsule right under it repeats. Today the amount is cut and the bar covers half the screen. The coach capsule under it wraps its CTA instead of cutting the message ("8 su…"), and its all-drafts message names the real months instead of a hard-coded "May's plan fits June".

Frontend only: `GET /budget/{month}` already returns `assigned_cents`, `spent_cents`, `rollover_cents` and `available_cents`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `budget-assignment`: the "Category assignment list" requirement now says how the three amounts are labeled and laid out, plus the carry-over line and the group subtotals.

## Impact

- **Webapp:**
  - `components/budget/AssignRow.tsx`: the row layout, the three columns, and the carry-over line;
  - `components/budget/AssignGroups.tsx`: the column headers and the subtotals;
  - `components/ui/TbaHero.tsx` and `app/globals.css`: the responsive classes for the row grid and the compact hero;
  - `components/ui/CoachCapsule.tsx`: the message wraps and the CTA moves under it on narrow screens;
  - `app/(app)/budgets/page.tsx`: the capsule's month names.
- **e2e:** a budget spec checks the labels, the Spent value and the carry-over line.
- **Docs:** `docs/user-guide.md`, in the glossary and the Budget section.
- **Unaffected:** the API, the backend, the coach, and the expanded row's formula breakdown.
