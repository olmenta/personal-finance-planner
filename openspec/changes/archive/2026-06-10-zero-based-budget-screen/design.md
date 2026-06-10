# Design — Zero-based budget screen

## Context

The current `/budgets` screen (from the Olmenta web kit) is a **spending report**: a donut of expense distribution plus spent-vs-limit category bars. That answers "where did my money go" — the passive bank-aggregator view that [project-definition.md](../../../project-definition.md) §2 explicitly calls out as failing for beginners.

The product method (§3) is **zero-based budgeting**: every euro of monthly income is assigned to a category until "to be assigned" reaches zero, unspent balances roll over, and the home screen must answer *"how much do I have left in each category this month?"*. The Olmenta design-system handoff contains **no reference design** for the assignment surface — this document fills that gap, staying inside Olmenta's visual language (violet/mint, Inter, white 24px-radius cards, tokens in `webapp/src/styles/tokens/`).

Decisions already made in exploration (2026-06-10):

- **Coach scope (v1):** no free-form chat. Coach components (CoachCapsule, CoachMessage) are the *skin* for the onboarding interview and proactive insight capsules only.
- **Goals** are deferred (§4.2); the goals screen is not part of this design.
- Build order: backend foundation → expense entry → **this screen** → AI onboarding. This screen will run on mock data first; the seeded default Spanish category tree stands in for the AI-generated one until onboarding lands.

## Goals / Non-Goals

**Goals:**

- One screen that drives the monthly assignment loop: see income pool → assign per category → reach **"to be assigned" = 0**.
- Make assignment feel like **confirming suggestions**, not filling a blank spreadsheet (§2): pre-fill from the previous month, one-tap accept-all.
- Always answer "how much is left per category" — available = assigned + rollover − spent, per row.
- Show rollover explicitly so envelope carryover is legible to a beginner.
- Work responsively: desktop (≥1024px sidebar layout) and phone (<1024px, bottom nav) from the same components.
- Euros only, es-ES formatting (`4.212,34 €`), tabular numerals everywhere.

**Non-Goals:**

- Savings goals UI (deferred, §4.2).
- Free-form coach chat (v1 coach = capsules + onboarding skin only).
- CSV import flows (separate change).
- Multi-currency (column exists in data model; UI is EUR-fixed).
- Backend implementation — this design defines the screen contract; models/endpoints land with the backend-foundation change.

## Decisions

### Decision 1: `/budgets` becomes "Budget" with two modes — Assign | Report

A `SegmentedControl` switches between **Assign** (new, default, the zero-based surface) and **Report** (the existing donut + bars, kept as-is). Why: the report view is already built and useful *after* assignment; making Assign the default mode puts the method first without throwing work away. Alternative considered: separate routes (`/budgets`, `/budgets/report`) — rejected, one mental place for "budget" beats two nav items, and the kit's mobile Report screen maps onto the same Report mode.

### Decision 2: "To be assigned" is the hero

A sticky hero band at the top (desktop: full-width card under the TopBar; mobile: sticky under the header) showing the single number the method optimizes:

```
┌──────────────────────────────────────────────────────────────┐
│  TO BE ASSIGNED            [ Confirm May's suggestions ]     │
│  412,00 €  ── violet, >0   (accent Button, shown while       │
│            of 2.350,00 € income     suggestions pending)     │
└──────────────────────────────────────────────────────────────┘
```

Three states drive its color and copy (money-direction semantics, never decorative):

| State | Value | Treatment | Copy |
|---|---|---|---|
| Unassigned | > 0 | violet (`--brand`), `.ol-money` | "412 € to assign" |
| Done | = 0 | mint (`--accent`), quiet celebration | "Every euro assigned" |
| Over-assigned | < 0 | expense red (`--expense`) | "−85 € over — unassign somewhere" |

Why hero: §3 defines the loop as "allocate until zero"; the screen must make the remaining distance impossible to miss. The mint zero-state is the reward moment (voice: celebrate quietly, no confetti).

### Decision 3: Assignment list = category groups with editable Assign cells

One `Panel` per `CategoryGroup`, rows composed from existing primitives plus one new cell type:

```
┌─ Vivienda ────────────────────────────────────────────────┐
│ [chip] Alquiler        Assigned   Spent     Available     │
│        ▓▓▓▓▓▓▓▓░░      [ 850 € ]  620 €     230 €  ●mint  │
│ [chip] Suministros     [ 120 € ]  138 €     −18 €  ●red   │
└───────────────────────────────────────────────────────────┘
```

- **Assigned** is the only editable cell — desktop: inline `AmountInput` (right-aligned, tabular, select-all on focus); mobile: tapping opens the **numpad bottom sheet shared with expense entry** (one numpad component, two consumers).
- **Available** = assigned + rollover − spent. Colored chip: mint > 0, gray = 0, expense-red < 0. The `BudgetBar` under the name shows spent/assigned progress (existing component, red when over).
- Row expands (chevron) to show the beginner-legible breakdown: `rollover from May 32 € + assigned 120 € − spent 138 € = −18 €` — rollover is taught in place, not in a help page.
- Per-row quick-fill menu: *Last month* · *Average (3m)* · *Spent last month* · *Zero*. These are the same heuristics the suggestion engine uses, exposed manually.

Alternative considered: spreadsheet-style table (YNAB). Rejected — §2's whole bet is that the spreadsheet feel is the abandonment cause; cards + one editable cell per row keeps it form-like.

### Decision 4: Suggestions are a confirmable draft, surfaced through the coach capsule

When a `BudgetMonth` opens, assignments arrive **pre-filled as a draft** (v1 heuristic: previous month's assignment; later the AI refines this). The coach insight capsule — per the coach-scope decision, this is exactly what capsules are for — sits under the hero:

```
( ✦  May's plan fits June — 2.350 € across 14 categories   Confirm all › )
```

- **Confirm all** accepts the draft → TBA recalculates → typically lands at/near 0.
- Any manual edit switches that row out of draft state; the capsule CTA becomes "Confirm remaining (n)".
- Dismissing the capsule keeps drafts editable; nothing is committed silently (mirrors §9: suggestions always require confirmation).

Why capsule and not a modal: assignment must feel optional-but-easy, not a gate; and it exercises the one coach surface v1 actually ships.

### Decision 5: Data contract (consumed, not implemented here)

The screen renders one payload per month; numbers are **integer cents**, formatted at render via `money()`/`euro()` (es-ES):

```
BudgetMonthView {
  month: "2026-06",
  income_cents: 235000,
  to_be_assigned_cents: 41200,          // derived: income − Σ assigned
  groups: [{
    id, name, sort_order,
    categories: [{
      id, name, icon, tone,
      assigned_cents, spent_cents, rollover_cents,
      available_cents,                  // derived: assigned + rollover − spent
      suggestion_cents, suggestion_state: "draft" | "confirmed" | "edited"
    }]
  }]
}
```

Mutations: `assign(category_id, month, amount_cents)` and `confirm_suggestions(month, [category_ids])`. Mock module (`webapp/src/lib/mock-data.ts`) implements this shape first so the API swap stays mechanical (CLAUDE.md convention).

### Decision 6: Responsive behavior

- **Desktop (≥1024px):** hero band + capsule + two-column group panels (`grid-dash-mid` pattern). Coach rail (≥1440px) shows assignment-related insights during this flow.
- **Phone (<1024px):** single column; hero collapses to a sticky compact bar (`To assign · 412 €`) on scroll; Assign cell opens the numpad sheet; FAB remains global expense entry (entry is a verb, not a place — it never navigates away from budget context, the sheet overlays).

## Risks / Trade-offs

- [Pre-filled drafts mask understanding — user confirms without learning the method] → the expandable row breakdown + first-month empty-state copy ("No May data yet — assign your first euro to Alquiler") teach mechanics in place; measure second-month retention (§8) as the canary.
- [Inline editing on desktop + sheet on mobile = two edit paths to maintain] → both wrap one `AmountInput` state contract; numpad sheet is shared with expense entry, so the cost is paid once.
- [TBA hero pinned + long category list = layout pressure on small phones] → compact sticky variant ≤64px; groups collapsible.
- [Report mode (donut) may still steal attention from Assign] → Assign is default; Report carries no badge/notification affordances.
- [Draft state adds a third assignment state (draft/confirmed/edited) to the data model] → contained in `suggestion_state`; backend can derive it, UI treats it as display metadata.

## Open Questions

- Income pool source before CSV/auth exist: manual "income this month" input, or seeded fixture? (Affects the hero's denominator.)
- Does "Confirm all" need an undo (snackbar) or is re-editing enough? Voice favors an easy out — "Deshacer" snackbar suggested.
- Group-level subtotals: show assigned/available per group header, or keep headers minimal? Suggest subtotals on desktop only.
- Where does Report mode's month picker live once TopBar already has one — unify on the TopBar picker? (Suggest: yes, single month context for the whole screen.)
