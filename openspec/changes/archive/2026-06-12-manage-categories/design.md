# Design — Manage income and expense categories

## Context

`Category` (id, user_id, group_id, name, icon, archived) and `CategoryGroup` (id, user_id, name, sort_order) exist since the core schema; the seed plants a default Spanish tree. The only endpoint is `GET /categories` (grouped, ordered by `sort_order`). Categories are referenced by `transactions.category_id` and `budget_assignments.category_id` — they can never be hard-deleted once used. Icons are lucide names rendered through the `Icon` name-map (`webapp/src/components/ui/Icon.tsx`); selection UIs (add transaction, import review) consume `GET /api/categories` via TanStack Query under the `["categories"]` key. There is no income/expense type on a category — direction lives on the transaction; one tree serves both.

## Goals / Non-Goals

**Goals:**

- Full tree editing: create/rename/re-icon/regroup/archive categories; create/rename/reorder/delete-empty groups.
- History safety: archiving never touches past transactions or budget months.
- One invalidation story: every mutation refreshes `["categories"]` (and budget for the current month, since names/icons render there).

**Non-Goals:**

- Hard-deleting categories or merging two categories (v1.x; merge needs a transaction-rewrite story).
- Per-category income/expense typing — direction stays on the transaction.
- Reordering categories inside a group (groups have `sort_order`; categories render in creation order — acceptable for v1).
- Drag-and-drop — explicit "move to group" select is enough and accessible.

## Decisions

### D1 — Archive is the only retire path

`PATCH /categories/{id}` with `archived: true` hides the category from selection UIs but keeps every FK valid; `archived: false` brings it back. No `DELETE /categories/{id}` at all — even an unused category is cheaper to archive than to special-case ("delete only if unused" creates a confusing fork where the same action sometimes destroys and sometimes hides). Budget view continues to include archived categories that have assignments or spending in the viewed month, so historical months render unchanged.

### D2 — Groups: explicit endpoints, delete only when empty

`POST /categories/groups` (name → `sort_order` = max+1), `PATCH /categories/groups/{id}` (rename, `sort_order`), `DELETE /categories/groups/{id}` → 204 only when the group has no categories (archived ones count as members); otherwise 409 `group_not_empty` — the user moves or archives the contents first, keeping the destructive surface tiny. Alternative rejected: cascade-archive on group delete — too much hidden behavior behind one button.

### D3 — Validation: per-group unique names, icon from the known map

Duplicate category name inside the same group → 409 `category_exists` (different groups may share a name: "Seguro" under Coche and Casa). Same per-user rule for group names → 409 `group_exists`. `icon` is any non-empty string ≤40 chars; unknown names degrade gracefully (the `Icon` component falls back to a circle), so the backend doesn't hard-code the lucide list. The icon picker in the UI offers `OLMENTA_ICON_NAMES` (already exported).

### D4 — Settings hosts the management UI

A "Categories" panel on the Settings screen renders the grouped tree (icon chip, name, archived badge) with a per-row actions menu (Rename / Change icon / Move to group / Archive–Unarchive) and per-group actions (Rename / Delete when empty), plus "Add category" / "Add group" buttons. Dialogs follow the `AddTransactionDialog` pattern; the icon picker is a simple grid of `OLMENTA_ICON_NAMES`. Settings is the natural home — budgets stays focused on assigning money, and the screen already exists. Mutations invalidate `["categories"]` and `["budget", currentMonth()]` (names/icons render in budget bars).

### D5 — `GET /categories` unchanged; clients filter

The list keeps returning everything with the `archived` flag rather than growing an `include_archived` parameter — the payload is tiny (tens of rows), and one shape means the management screen, pickers, and budget join all share the same cached query. Selection UIs filter `archived` client-side.

## Risks / Trade-offs

- [Archiving a category that the current month still budgets] → assignment stays visible in the budget view for months with activity; the user can move money off it like any other category.
- [Two in-flight changes modify the same `bff-proxy` requirement (`edit-delete-transactions` is active)] → whichever syncs second must merge the endpoint list rather than overwrite; noted in tasks.
- [Unknown icon strings] → Icon component falls back to `circle`; no render break.
- [Concurrent rename collisions] → unique checks are per-request; last write wins is acceptable single-user v1.

## Migration Plan

1. Backend mutations + tests (additive).
2. BFF routes + api.ts helpers.
3. Settings UI + archived filtering in pickers.
Rollback: revert webapp commit; backend endpoints additive; no migration.

## Open Questions

- None blocking.
