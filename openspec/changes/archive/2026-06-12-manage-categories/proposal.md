# Proposal — Manage income and expense categories

## Why

The category tree is frozen at seed time: users cannot create, rename, regroup, or retire categories, even though every transaction, budget assignment, and AI suggestion hangs off them. Project-definition v1 feature 2 commits to "categories editable afterwards (create, rename, archive, group)" — and the upcoming AI-onboarding tree only makes sense if the user can correct it afterwards.

## What Changes

- **Category CRUD**: `POST /categories` (name, icon, group), `PATCH /categories/{id}` (rename, change icon, move to another group, archive/unarchive). No hard delete — transactions and budget assignments reference categories, so retiring is archiving: the category disappears from selection UIs but history and past budgets stay intact.
- **Group management**: `POST /categories/groups` (create), `PATCH /categories/groups/{id}` (rename, reorder), `DELETE /categories/groups/{id}` (only when empty — otherwise 409).
- **List stays the single read**: `GET /categories` keeps returning the full tree with the `archived` flag; selection UIs (add/edit transaction, import review) exclude archived categories client-side, while the budget view keeps showing archived categories that still have activity.
- **Management UI**: a "Categories" section on the Settings screen — grouped tree with inline actions (add category, add group, rename, change icon, move group, archive/unarchive, delete empty group), using the existing dialog patterns and the lucide icon name-map for icon picking.
- **BFF**: new Route Handlers for the category and group mutation endpoints.

## Capabilities

### New Capabilities

- `categories-api`: the category tree contract — grouped list, category create/update/archive, group create/update/delete-when-empty.

### Modified Capabilities

- `bff-proxy`: proxied-routes requirement gains the category/group mutation routes.
- `webapp-server-state`: new requirement — category management flow on Settings with cache invalidation; selection UIs exclude archived categories.

## Impact

- `backend/app/routers/categories.py`: mutation handlers; `schemas.py`: create/update payloads.
- `backend/tests/`: new `test_categories.py` (CRUD, archive semantics, non-empty group delete 409, cross-user 404).
- `webapp/src/app/api/categories/*`: new Route Handlers.
- `webapp/src/lib/api.ts`: types + helpers; `AddTransactionDialog`/import review/`EditTransactionDialog` (in-flight change) filter archived.
- `webapp/src/app/(app)/settings/page.tsx`: Categories management section + dialogs.
- No schema migration — `Category.archived`, `CategoryGroup.sort_order` already exist.
