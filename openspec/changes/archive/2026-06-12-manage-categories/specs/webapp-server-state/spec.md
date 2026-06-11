# webapp-server-state Delta Specification

## ADDED Requirements

### Requirement: Category management on Settings

The Settings screen SHALL offer a "Categories" section rendering the grouped tree with actions to add a category (name, icon from the Olmenta icon map, group), add a group, rename, change icon, move a category to another group, archive/unarchive a category, and delete an empty group. Every mutation SHALL invalidate the categories query and the current budget month query. Selection UIs (transaction dialogs, import review) SHALL exclude archived categories, while the management section and historical views keep showing them flagged.

#### Scenario: New category usable immediately

- **WHEN** the user adds "Mascotas" from Settings and then opens "Add transaction"
- **THEN** the category select offers "Mascotas" without a page reload

#### Scenario: Archived category leaves the pickers

- **WHEN** the user archives "Ocio"
- **THEN** the transaction dialogs and import review no longer offer it, while Settings still lists it with an archived badge and an unarchive action

#### Scenario: Non-empty group delete surfaces the rule

- **WHEN** the user tries to delete a group that still has categories
- **THEN** the UI explains the group must be empty first and offers no destructive fallback
