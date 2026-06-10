# Tasks — Zero-based budget screen

## 1. Data layer (mock contract)

- [x] 1.1 Add `BudgetMonthView` types to `webapp/src/lib/mock-data.ts` — integer cents, groups → categories with `assigned_cents`, `spent_cents`, `rollover_cents`, `suggestion_cents`, `suggestion_state` (per design.md Decision 5)
- [x] 1.2 Build June 2026 mock month (Spanish category groups: Vivienda, Comida, Transporte, Suscripciones…) with May data so drafts pre-fill; include one overspent category and an over-assign path for testing hero states
- [x] 1.3 Add a `useBudgetMonth` client hook with local-state mutations: `assign(categoryId, cents)`, `confirmSuggestions(categoryIds)` — derives `to_be_assigned_cents` and `available_cents`

## 2. New primitives

- [x] 2.1 `AmountInput` (`webapp/src/components/ui/AmountInput.tsx`): right-aligned tabular euro input, select-all on focus, commits on blur/Enter, es-ES parsing (comma decimals)
- [x] 2.2 `NumpadSheet` (`webapp/src/components/ui/NumpadSheet.tsx`): bottom-sheet numpad for <1024px amount editing — designed for reuse by the future expense-entry flow
- [x] 2.3 `TbaHero` (`webapp/src/components/ui/TbaHero.tsx`): to-be-assigned band with the three states (violet >0 / mint =0 "Every euro assigned" / red <0), income denominator, sticky-compact variant for mobile

## 3. Assignment surface

- [x] 3.1 `AssignRow` component: IconChip + name, editable assigned cell (AmountInput desktop / NumpadSheet mobile), spent, available chip colored by sign, BudgetBar progress, draft-state styling
- [x] 3.2 Expandable row breakdown: `rollover + assigned − spent = available` with actual amounts
- [x] 3.3 Per-row quick-fill menu: Last month · Average (3m) · Spent last month · Zero
- [x] 3.4 Group panels: one Panel per CategoryGroup composing AssignRows; desktop subtotals in group header

## 4. Screen assembly

- [x] 4.1 Rebuild `webapp/src/app/(app)/budgets/page.tsx`: SegmentedControl Assign | Report; Assign default; existing donut/report preserved as Report mode; single month context from TopBar picker
- [x] 4.2 Wire the coach capsule to drafts: "May's plan fits June — Confirm all ›", count updates as rows are edited, dismissal keeps drafts (spec: dismissal ≠ confirmation)
- [x] 4.3 First-month empty state: zero assignments, directional copy inviting the first assignment, no capsule
- [x] 4.4 Responsive pass: sticky compact TBA bar on mobile scroll, single-column groups <1024px, sheet editing; add needed utility classes to `globals.css`

## 5. Verify

- [x] 5.1 Walk the spec scenarios manually: hero three states, row math (rollover 32 + assigned 120 − spent 138), edit flows desktop/mobile, confirm-all, partial edits, dismissal, mode switch keeps month
- [x] 5.2 `volta run npm run build` green; no token/visual regressions on other screens
