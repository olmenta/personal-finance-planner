# Proposal — Zero-based budget screen

## Why

The current `/budgets` screen is a spending report (donut + spent-vs-limit bars) — the passive "where did my money go" view that [project-definition.md](../../../project-definition.md) §2 identifies as the reason beginners abandon finance apps. The product's core method (§3, MVP feature #3) — zero-based monthly assignment with a "to be assigned" indicator, suggested allocations, and rollover — has no UI at all. This screen is the heart of v1 and the key retention lever (second-month budget creation, §8).

## What Changes

- `/budgets` becomes a two-mode "Budget" screen: **Assign** (new, default — the zero-based surface) and **Report** (the existing donut/bars view, kept).
- New **"To be assigned" hero**: sticky band showing `income − Σ assigned`, with three money-semantic states (violet > 0, mint = 0 "Every euro assigned", red < 0 over-assigned).
- New **assignment list**: one panel per category group; each row shows assigned (editable), spent, rollover and available (`assigned + rollover − spent`); expandable breakdown teaches rollover in place; per-row quick-fill (last month / 3-month average / spent last month / zero).
- **Suggested assignments as a confirmable draft**, surfaced through the coach insight capsule ("May's plan fits June — Confirm all"); nothing commits without confirmation (§9).
- Mobile (<1024px): single column, compact sticky "to assign" bar, assignment editing via a numpad bottom sheet shared with the future expense-entry flow.
- Screen runs on mock data implementing the `BudgetMonthView` contract (integer cents); backend endpoints land with a separate backend-foundation change.

## Capabilities

### New Capabilities

- `budget-assignment`: monthly zero-based assignment — the "to be assigned" indicator and its states, editable per-category assignments, available/rollover math, and the assignment list layout.
- `budget-suggestions`: draft assignments proposed from prior-month data, confirmable in bulk via the coach capsule or edited per row; never auto-committed.

### Modified Capabilities

<!-- none — no existing specs in openspec/specs/ yet -->

## Impact

- `webapp/src/app/(app)/budgets/page.tsx`: rebuilt as two-mode screen (Assign default, Report preserved).
- `webapp/src/components/ui/`: new `AmountInput`, `AssignRow`, `TbaHero` primitives; reuses Panel, IconChip, BudgetBar, Badge, SegmentedControl, CoachCapsule.
- `webapp/src/lib/mock-data.ts`: new `BudgetMonthView` mock (integer cents) + mutation stubs; existing formatted-string mocks for budgets migrate to it.
- `webapp/src/app/globals.css`: sticky-hero and assignment-grid utility classes.
- No backend, auth, or i18n changes in this change; data contract documented in design.md for the later backend-foundation change.
