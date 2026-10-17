# category-matching Specification

## Purpose
TBD - created by archiving change coach-budget-setup. Update Purpose after archive.
## Requirements
### Requirement: Finding similar categories and groups

The backend SHALL have one service that, given a name, returns the user's similar active categories (or non-system groups), at most 5, best first. Names are compared folded (case- and accent-insensitive, trimmed, inner spaces collapsed). A candidate SHALL match when, in this order of strength:

1. **`same_name`:** the folded names are equal;
2. **`contains`:** one folded name contains the other, with at least 3 characters;
3. **`shared_word`:** they share a word of at least 4 letters, ignoring Spanish stop words ("de", "del", "la", "el", "los", "las", "y", "en", "para");
4. **`close_spelling`:** their similarity ratio is at least 0.8 (a typo or a plural).

The chat and the MCP server SHALL use this service; neither SHALL create a category or group without running it first.

#### Scenario: Case and accents

- **WHEN** the name is "transporte publico" and "Transporte público" exists
- **THEN** it matches with `same_name`

#### Scenario: A plural or typo

- **WHEN** the name is "Suscripcion" and "Suscripciones" exists
- **THEN** it matches (`contains` or `close_spelling`)

#### Scenario: Shared word

- **WHEN** the name is "Seguro del coche" and "Seguro hogar" exists
- **THEN** "Seguro hogar" matches with `shared_word`

#### Scenario: Unrelated names

- **WHEN** the name is "Veterinario" and the tree is the default one
- **THEN** there are no matches

### Requirement: Suggested group for a new category

For a new category name, the service SHALL suggest a group: the group of the best similar category when there is one; otherwise the non-system group whose categories share the most words with the name; otherwise the last non-system group. The chat and the MCP server SHALL show the suggestion but let the user choose any existing non-system group or a new one.

#### Scenario: Suggested from a similar category

- **WHEN** the name is "Súper" and "Supermercado" is in "Comida"
- **THEN** the suggested group is "Comida"

#### Scenario: Nothing similar

- **WHEN** nothing is similar to "Veterinario"
- **THEN** a non-system group is suggested, and the user can still pick another

