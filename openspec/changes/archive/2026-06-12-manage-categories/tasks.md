# Tasks — Manage income and expense categories

## 1. Backend API

- [x] 1.1 Schemas in `backend/app/schemas.py`: `CategoryCreate` (name, icon, group_id), `CategoryUpdate` (all optional: name, icon, group_id, archived), `GroupCreate`, `GroupUpdate` (name, sort_order)
- [x] 1.2 `POST /categories` + `PATCH /categories/{id}` in `backend/app/routers/categories.py`: owner-scoped 404s, per-group duplicate name → 409 `category_exists`, move-to-group validates target group, archive/unarchive (design D1, D3)
- [x] 1.3 Group endpoints: `POST /categories/groups` (sort_order = max+1), `PATCH /categories/groups/{id}`, `DELETE /categories/groups/{id}` empty-only else 409 `group_not_empty`; duplicate group name → 409 `group_exists` (design D2)
- [x] 1.4 `backend/tests/test_categories.py`: create/rename/move/re-icon, archive keeps transactions and past budget months intact, unarchive restores, duplicate names 409, foreign/unknown ids 404, group create/rename/reorder, delete empty 204 vs non-empty (incl. archived member) 409; `uv run pytest` green

## 2. BFF and client

- [x] 2.1 Route Handlers: extend `webapp/src/app/api/categories/route.ts` with POST; add `[id]/route.ts` (PATCH), `groups/route.ts` (POST), `groups/[id]/route.ts` (PATCH, DELETE)
- [x] 2.2 `webapp/src/lib/api.ts`: payload types + `createCategory`, `updateCategory`, `createCategoryGroup`, `updateCategoryGroup`, `deleteCategoryGroup`

## 3. Settings UI

- [x] 3.1 "Categories" section on `webapp/src/app/(app)/settings/page.tsx`: grouped tree (IconChip, name, archived Badge), per-row actions menu (Rename / Change icon / Move to group / Archive–Unarchive), per-group menu (Rename / Delete when empty), "Add category" + "Add group" buttons (design D4)
- [x] 3.2 Dialogs following the `AddTransactionDialog` pattern: category create/edit (name input, icon picker grid from `OLMENTA_ICON_NAMES`, group select), group create/rename; destructive delete-empty-group confirmation; 409 errors surfaced as actionable messages
- [x] 3.3 Mutations invalidate `["categories"]` + `["budget", currentMonth()]`; selection UIs filter `archived` (AddTransactionDialog, import review dialog, and the in-flight EditTransactionDialog if landed)

## 4. Verification

- [x] 4.1 `uv run pytest` green (TEST_DATABASE_URL exported); `volta run npm run build` + `volta run npm run lint` green
- [x] 4.2 E2E with both processes: add group + category from Settings → appears in add-transaction select; archive a category with history → gone from pickers, history intact, budget month unchanged; delete empty group works, non-empty blocked with message
- [x] 4.3 At sync/archive time: merge the `bff-proxy` proxied-routes list with whatever `edit-delete-transactions` has landed (both changes modify the same requirement)
