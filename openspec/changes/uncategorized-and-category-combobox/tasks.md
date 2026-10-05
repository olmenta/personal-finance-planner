# Tasks — Uncategorized Spending & Category Combobox

## 1. Backend: uncategorized spending in the budget view

- [x] 1.1 `schemas.py`: `BudgetMonthView.uncategorized_cents` and `uncategorized_count` (int, default 0)
- [x] 1.2 `services/budget_view.py`: one grouped `SUM`/`COUNT` query over the month's confirmed outflows with no category, no `transfer_pair_id` and `source != "opening_balance"`, on every account (design D1); fill both fields without touching any other figure
- [x] 1.3 Tests in `tests/test_budget.py`:
  - bank and card uncategorized rows are counted
  - transfer twins and opening debt are not counted
  - categorizing a row moves its amount into the category's spent and raises To Be Assigned
  - the budget identity still holds

## 2. Webapp: category picker

- [x] 2.1 Add shadcn `popover` and `command` with `volta run npx shadcn@latest add popover command`. They must land in `components/shadcn/`; check that `cmdk` is in `package.json`.
- [x] 2.2 `components/CategoryCombobox.tsx` (design D3):
  - controlled `value`/`onChange`
  - `allowNone` with a label, and `extraGroups` (for "Transfers →")
  - reads the `["categories"]` query
  - leaves out archived categories and system groups
  - groups shown as headings, with cmdk search and keyboard support
- [x] 2.3 Inline creation (design D4):
  - "Crear «X»" is offered only when no exact case-insensitive match exists
  - an in-popover form with the name and a group select, preselected from `localStorage` key `olmenta-last-category-group` (falling back to the first non-system group; storage access wrapped in try/catch)
  - creation goes through `createCategory`, then `setQueryData` on `["categories"]`, then invalidate
  - the new category is selected
  - on 409 `category_exists`, select the existing category instead
- [x] 2.4 Replace the category `Select` in `AddTransactionDialog` and `EditTransactionDialog`
- [x] 2.5 Replace the category `Select` in `SuggestCategoriesDialog`

## 3. Webapp: import review

- [x] 3.1 Extract `ImportReviewRow` as `React.memo` (design D5):
  - props: the row, its own selection/payee/note/decision, and shared stable lists
  - callbacks: stable `(rowId, value)` dispatchers created with `useCallback`
  - add a comment stating the stable-props contract
- [x] 3.2 Use `CategoryCombobox` in the row, with "Transfers →" through `extraGroups` and "Ready to assign"/"Uncategorized" through `allowNone`. Keep the transfer, match, note and payee behavior unchanged.
- [x] 3.3 Check by hand: in a review of 100+ rows, typing a note or payee keeps up with the keyboard, and a category created in one row is listed in the next row's picker

## 4. Webapp: "Sin categorizar" on the budget

- [x] 4.1 `lib/api.ts`: add `uncategorized_cents` and `uncategorized_count` to `BudgetMonthView`
- [x] 4.2 Budget page:
  - render the "Sin categorizar" block above the groups when `uncategorized_count > 0`: warning style (not `--expense`), total, count, and a "Categorizar ahora" button
  - the button calls `suggestCategories` and opens `SuggestCategoriesDialog` on the page (design D2)
  - nothing else is blocked
- [x] 4.3 After apply, invalidate the budget month (already done by the dialog's apply via `invalidateMoneyQueries`), and check the block disappears when the count reaches 0

## 5. Specs-only

- [x] 5.1 Confirm `services/summary.py` matches the corrected summary-api wording (uncategorized outflows counted, transfers and opening balances excluded). Add a test in `tests/test_summary*.py` for an uncategorized outflow in `expense_cents` and its week bucket.

## 6. Verification

- [x] 6.1 `uv run pytest` green in `backend/`
- [x] 6.2 Type check, lint and build green in `webapp/`. Build with `NEXT_DIST_DIR=.next-verify` while a dev server is running, then revert any `tsconfig.json` rewrite.
- [x] 6.3 `volta run npm run e2e` green. Add a Playwright check that types into a note in a multi-row import review and asserts the value keeps up.
- [x] 6.4 Manual:
  - create a category from the import review and pick it in the next row
  - search categories in Add transaction
  - confirm an uncategorized expense, see "Sin categorizar" on the budget, use "Categorizar ahora", and watch the block disappear
