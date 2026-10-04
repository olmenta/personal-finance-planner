# categories-api Specification

## Purpose

The category tree contract: grouped list shared by management, pickers, and the budget join; category create/update with archive as the only retire path; group create/update/delete-when-empty.

## Requirements

### Requirement: Grouped category tree

The API SHALL expose `GET /categories` returning the user's category groups ordered by `sort_order`, each with its categories including `id`, `name`, `icon`, and `archived`. Archived categories SHALL be included (flagged) so management and historical views share one read.

#### Scenario: Tree returned grouped and ordered

- **WHEN** a client requests `GET /categories`
- **THEN** groups arrive in `sort_order` with their categories and each category carries its `archived` flag

### Requirement: Create and edit categories

The API SHALL expose `POST /categories` (name, icon, `group_id`) returning 201, and `PATCH /categories/{id}` updating any of `name`, `icon`, `group_id` (move between groups), and `archived`. Archiving SHALL be the only retire path — there is no category delete — and SHALL leave all referencing transactions and budget assignments untouched; unarchiving restores the category to selection UIs. A duplicate name within the same group SHALL return 409 `category_exists`; an unknown or foreign category or target group SHALL return 404.

#### Scenario: Category created in a group

- **WHEN** the user creates "Mascotas" with icon `circle` in group "Estilo de vida"
- **THEN** the API returns 201 and `GET /categories` lists it under that group

#### Scenario: Renamed and moved

- **WHEN** a category is patched with a new `name` and another group's `group_id`
- **THEN** the tree shows it under the new group with the new name and all its transactions keep pointing at it

#### Scenario: Archive hides but preserves history

- **WHEN** a category with past transactions is archived
- **THEN** it is flagged `archived` in the tree, its transactions still list with its name, and past budget months render unchanged

#### Scenario: Duplicate name in the same group rejected

- **WHEN** a category named "Supermercado" is created in a group that already has one
- **THEN** the API returns 409 with code `category_exists`

### Requirement: Manage category groups

The API SHALL expose `POST /categories/groups` (name, appended at the end of the order), `PATCH /categories/groups/{id}` (rename, `sort_order`), and `DELETE /categories/groups/{id}` which SHALL succeed (204) only when the group contains no categories — archived members count — and otherwise return 409 `group_not_empty`. A duplicate group name for the user SHALL return 409 `group_exists`.

#### Scenario: Group created at the end

- **WHEN** the user creates a group "Coche"
- **THEN** it appears after the existing groups in the tree

#### Scenario: Non-empty group cannot be deleted

- **WHEN** `DELETE /categories/groups/{id}` targets a group that still has an archived category
- **THEN** the API returns 409 with code `group_not_empty`

#### Scenario: Empty group deleted

- **WHEN** the user moves every category out of a group and deletes it
- **THEN** the API returns 204 and the group leaves the tree

### Requirement: Category kind and savings flag

`GET /categories` SHALL include each category's derived `kind` (`scheduled` | `savings` | `flexible`, see payment-schedules) and its `savings` flag. `POST /categories` and `PATCH /categories/{id}` SHALL accept an optional boolean `savings` (default false on create); a non-boolean value SHALL return 422. The kind itself SHALL NOT be writable.

#### Scenario: Mark a category as savings

- **WHEN** a client patches "Ahorro Tomy" with `savings = true`
- **THEN** the tree lists it with `savings = true` and `kind = "savings"`

#### Scenario: Invalid flag rejected

- **WHEN** a client patches a category with `savings = "maybe"`
- **THEN** the API returns 422
