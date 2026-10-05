# Design — Uncategorized Spending & Category Combobox

## Context

- **Budget plane today:** an uncategorized outflow on a cash or bank account counts as "unbudgeted activity". It lowers `to_be_assigned_cents` (see the budget-api identity) but appears in no category row. An uncategorized outflow on a credit account is card debt and never reaches To Be Assigned. The only place these rows surface is the transactions screen, through the "Suggest categories" button (`SuggestCategoriesDialog`, fed by `POST /transactions/suggest-categories` and `apply-categories`).
- **Summary:** `services/summary.py` already computes expenses as every confirmed outflow plus categorized inflows, with transfers and `opening_balance` rows excluded. Only the spec says "categorized".
- **Pickers:** four places render a Radix `Select` with every active category grouped by category group: the import review row, Add and Edit transaction, and the AI review row. None can search or create.
- **Performance:** `ImportBankTransactionsDialog` keeps `selections`, `payeeEdits`, `noteEdits` and `matchDecisions` in the dialog component and renders every row inline. A keystroke in one row's note or payee therefore re-renders all rows. Each row carries a Radix `Select`, which mounts a hidden native `<select>` with all categories, plus a `PayeeField`. With dozens of rows and categories that is thousands of nodes per keystroke.
- **Decisions already made with the user (2026-10-04):**
  - "Sin categorizar" is shown prominently, but nothing is blocked.
  - Inline creation asks for the group, preselected with the last one used.
  - The combobox goes in every picker.

## Goals / Non-Goals

**Goals:**

- Every uncategorized euro of spending is visible on the budget screen, with a one-tap path to categorize it.
- The dashboard and the spec agree on what "expenses" means.
- Categories can be found by typing and created without leaving the flow.
- Typing in the import review keeps up with the keyboard on a statement of a few hundred rows.

**Non-Goals:**

- Changing budget math: To Be Assigned, rollover and the identity stay exactly as specified.
- Blocking assignment, moves or import confirmation while rows are uncategorized.
- A payee combobox, list virtualization, or server-side category search.

## Decisions

### D1: Uncategorized spending is a reported figure, not a category

**Choice:** `BudgetMonthView` gains two fields, `uncategorized_cents` and `uncategorized_count`.

- **What they count:** the month's confirmed outflows with `category_id IS NULL`, `transfer_pair_id IS NULL` and `source != 'opening_balance'`. Accounts of every type count, credit included: an uncategorized card purchase also needs a category, and once it gets one, the credit-card funded-move rules apply.
- **How it's computed:** one grouped `SUM`/`COUNT` query next to the existing activity queries.
- **What the client renders:** the block above the groups.

**Alternative rejected:** a synthetic "Sin categorizar" category inside `groups`. It would have to report `assigned`, `available` and `rollover`, which all mean nothing for it. It would also break the identity (`TBA + Σ available + Σ credit_overspent`), because those euros are already out of To Be Assigned. And it would leak into moves, cover suggestions and quick-fill.

**Effect of categorizing a row:** TBA rises by the amount and the chosen category's `spent` rises by the same amount (for a cash or bank row). The identity holds before and after.

### D2: "Categorizar ahora" reuses the AI review on the budget page

The budget page hosts the same flow the transactions screen has: `suggestCategories()` → `SuggestCategoriesDialog` → apply.

- The dialog component already takes `proposals` and handles apply plus invalidation. The page owns a small mutation and the dialog state.
- When AI is unavailable, the dialog's existing empty state points to manual categorization, and the block also links to `/transactions` for that.

**Alternative rejected:** navigating to `/transactions?categorize=1`. It costs an extra screen and a query-param side effect, and the user loses the budget context they were looking at.

### D3: One `CategoryCombobox` on shadcn `popover` + `command` (cmdk)

**Choice:** a controlled component, `value: string | null` and `onChange(id)`, plus `allowNone` (with a configurable "none" label: "Ready to assign" / "Uncategorized") and `extraGroups` (used for the import review's "Transfers →" entries, so that path stays one control). These primitives are added with the shadcn CLI and land in `components/shadcn/`.

- **Search:** cmdk's fuzzy filter matches on category names, and groups stay as `CommandGroup` headings.
- **Data source:** the shared `["categories"]` query. Archived categories and `system` groups are filtered out in one place.

**Alternative rejected:** a hand-rolled input plus listbox. Keyboard navigation, ARIA roles and focus handling are exactly what cmdk gives us for free.

### D4: Inline creation, with the group asked and remembered per viewer

When the query has no exact (case-insensitive) match, the list ends with "Crear «<query>»".

- **The form:** choosing it swaps the list for a compact form inside the popover: the name (prefilled, editable), a group select, and "Crear categoría".
- **The group default:** the last group used, stored in `localStorage` under `olmenta-last-category-group`. It falls back to the first non-system group, and an unavailable store also falls back.
- **On success:**
  1. `POST /api/categories` creates the category.
  2. The new category is written into the `["categories"]` cache with `setQueryData`, so every mounted picker shows it in the same render.
  3. Then the query is invalidated.
  4. The new id is selected in the originating row.
- **On 409 `category_exists`:** the existing category is selected instead.

**Alternative rejected:** a fixed "Otros" group. The user chose to keep the tree ordered.

### D5: Import review rows are memoized components with stable callbacks

**Choice:** extract `ImportReviewRow` as `React.memo`.

- **Its props:** the row object (stable identity from the batch query), its own current values (`selection`, `payee`, `note`, `decision`), plus shared, referentially stable lists: categories, payees, transfer targets and account names.
- **Its callbacks:** dispatchers created once (`useCallback`) that take `(rowId, value)`, so no row receives a new function identity when another row changes.
- **State shape:** the per-row state maps stay in the dialog because confirm needs them all. A keystroke now changes one map entry: only that row's props differ, and only that row re-renders.
- **Cost of the combobox:** its options mount only while its popover is open, which removes the per-row hidden `<select>`.

**Alternative rejected:** uncontrolled inputs read through refs on confirm. They work, but they fight the existing "resume pending review" state and make the transfer and match logic harder to follow.

### D6: Summary spec catches up with the code

`expense_cents` is specified as the absolute net of every confirmed outflow plus categorized inflows in the month, with transfers and opening balances excluded. No code change.

- Week buckets follow the same rule.
- The dashboard's spending is "everything that left", and the budget's "Sin categorizar" block explains the part no category shows.

## Risks / Trade-offs

- **[Credit uncategorized rows counted in the block but not in TBA]** → The block is "spending that needs a category", not a TBA reconciliation. The copy says exactly that.
- **[cmdk fuzzy matching surprises]** (e.g. "gas" matching "Gastos varios") → An exact match is still listed, and "Crear «X»" appears only when there is no exact name match.
- **[Two places create categories]** (Settings and the picker) → Both call `POST /categories`, so the uniqueness rule (409 `category_exists`) is shared.
- **[Memoization silently broken by a new inline prop later]** → A comment on the row component names the stable-props contract. A Playwright check types into a note field of a multi-row review and asserts the value keeps up.
- **[New dependency: cmdk]** → It is small, it is the standard shadcn combobox base, and it has no runtime network access.

## Migration Plan

Additive only: new response fields and new UI. There is no migration. Rollback means reverting the commit; older clients ignore the new fields.

## Open Questions

None. All three product decisions were taken with the user.
