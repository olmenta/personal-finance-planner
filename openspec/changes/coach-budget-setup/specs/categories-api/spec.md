## ADDED Requirements

### Requirement: Similar categories

The API SHALL expose `GET /categories/similar?name=<text>&kind=category|group` returning, for the user's active (non-archived) categories or non-system groups, the ones similar to `name` as defined by category-matching. Each result SHALL carry its id, name, group (for categories), and why it matched (`same_name`, `contains`, `shared_word`, `close_spelling`). For categories, the response SHALL also carry the suggested group for a new category with that name. An empty or blank name SHALL return 422.

#### Scenario: Similar categories listed

- **WHEN** the client requests `GET /categories/similar?name=super`
- **THEN** the response lists "Supermercado" in group "Comida" with reason `contains`, and the suggested group is "Comida"

#### Scenario: Nothing similar

- **WHEN** the client requests `GET /categories/similar?name=Veterinario` and no category shares a word or a close spelling
- **THEN** the response has no matches and suggests a group that isn't a system group
