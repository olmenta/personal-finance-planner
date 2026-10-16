## Context

`coach-conversation-actions` gave Home a coach with typed tools and a safe action lifecycle (preview → confirm → atomic apply → undo). It can record a transaction in a known category, set one day-to-day amount, and move money. It can't create categories or groups, and it can't set several amounts at once, so it can't help someone build a budget. The dev MCP server (12 tools over the REST API) can create a category, but blindly.

**What exists and is reused:**

- `coach_actions`: dry-run preview, revision, idempotent commit under the month lock, undo.
- `coach_tools`: name resolution and `CoachDeps`.
- `budget_moves.set_assignment`: the assignment PUT rules, including `assignment_from_payments`.
- `entries.create_entry`.
- The categories router (create category and group, uniqueness codes).
- `category_setup.ensure_category` and `ensure_group`.
- The MCP server's `resolve` and `OlmentaClient`.

## Goals / Non-Goals

**Goals:**

- No category or group is ever created without first showing similar ones and getting the user's choice, in the chat and in the MCP server.
- A new category is created in a group the user chose; the suggestion is only a default.
- One confirmation for a whole budget ("pon 300 en el súper, 80 en gasolina…").
- Transactions in any account, cash included, with the same 5-second feel.

**Non-Goals:**

- Creating or editing **payment schedules** from the chat (rent, insurance). The coach still points to Budget → a category's payments. See Open Questions.
- Renaming, merging, archiving or moving categories from the chat.
- Semantic matching with embeddings: the model adds meaning-based matches, limited to existing categories.
- Changing the onboarding interview.

## Decisions

### D1. One matching service, exposed for the MCP server

`services/category_matching.py`:

- `similar_categories(db, user, name) -> list[Match]`;
- `similar_groups(db, user, name) -> list[Match]`;
- `suggest_group(db, user, name, matches) -> group`.

The rules are the spec's: fold, `same_name`, `contains`, `shared_word` (Spanish stop words ignored), and `close_spelling` (difflib ratio ≥ 0.8). Results are ranked by rule strength and then ratio, at most 5.

`GET /categories/similar?name=&kind=` exposes it, because the MCP server only talks to the REST API. The coach tools call the service in-process.

- **Alternative:** have the LLM judge similarity alone. Rejected: it's not guaranteed, and the rule has to hold even for the MCP server's host models.
- **Alternative:** embeddings. Rejected: a new dependency, plus data sent out for a small tree. The model's `similar` hint covers meaning ("veterinario" ~ "Mascotas"), and the server only accepts existing names.

### D2. `category` action kind with a choice, and a follow-up

`propose_category(name, group?, similar?, for?)` stores a `CoachAction(kind="category")`:

- **command:** `{name, suggested_group_id, similar: [ids], for: <a transaction or assignment command without category>}`.
- **preview:** `{name, similar: [{id, name, group, reason}], groups: [{id, name}], suggested_group_id}`.
- **revision:** a hash of the preview, so a category created elsewhere in the meantime makes it stale.

The widget is `category_choice`. Two endpoints resolve it:

- **`POST /coach/actions/{id}/resolve {category_id}`** ("Use X"): the category must be one of the user's active categories, not necessarily one listed, because the dropdown could offer any later. It marks the action `resolved`, a new terminal status (no undo), with `result.category_id`. If `for` is set, it proposes the follow-up with that category and returns it.
- **`POST /coach/actions/{id}/commit`** with `group_id` or `new_group_name`:
  - a new group runs `similar_groups`, and a same-name group is reused instead of duplicated;
  - it creates the category through the categories service (same uniqueness codes) and records `result.category_id` (and `result.group_id` with `created_group`);
  - it proposes the follow-up.

  The commit body extends `CoachCommitIn` with optional `group_id` and `new_group_name`; other kinds ignore them.

The follow-up is a normal proposed action (transaction or assignment) returned in the response and added to the message's widgets after the choice. So the user always confirms the money change separately.

- **Alternative:** auto-confirm the expense together with the category. Rejected: two different decisions, and the 5-second promise holds with two taps.

**Undo for `category`:** allowed while nothing uses the category (no transactions, no assignment above zero, no schedule). Undo archives the category, and the group too if it was created by this action and is empty. Nothing is deleted, per the categories spec.

### D3. `assignments` action kind

`propose_budget([{category, amount}])` builds `{kind: "assignments", month, items: [{category_id, category_name, amount_cents}]}`. The preview, commit and undo reuse the existing machinery: `_touched` returns every item, `_apply` calls `set_assignment` per item, and undo restores each `before`. The tool validates up front: unknown names give the resolution error, and categories with payments or that aren't day-to-day give `assignment_from_payments` / `not_day_to_day` for the whole call, so the model resends without them.

The single-category `assignment` kind stays as it is.

### D4. Accounts by name or type

The `propose_transaction` account resolution tries names first (the existing resolver). If no name matches, it maps type words to account types:

| Words | Type |
|---|---|
| "efectivo", "cash", "metálico" | cash |
| "tarjeta", "card", "crédito" | credit |
| "banco", "cuenta", "bank" | bank |

It picks the single active account of that type. With two or more, the error lists them so the model asks. The MCP server's `_account_id` gets the same fallback through the shared helper in `services/names.py`, mirrored in `mcp_server/resolve.py`, which can't import app code.

### D5. MCP server

- **`find_categories(name)`:** calls `/categories/similar`.
- **`create_category(name, group?, confirmed_new=false)`:**
  - without `group`, it returns the groups and the suggestion;
  - on an exact match, it returns the existing category;
  - with similar ones and no confirmation, it returns them with the instruction to ask;
  - otherwise it creates.
- **`create_group(name, confirmed_new=false)`:** the same flow on groups.
- **`set_budget(items, month?)`:** sequential `PUT`s. It validates every name first, so a bad name writes nothing. The REST API has no batch endpoint, so a mid-way API failure can leave a partial write, and the result says which items were set. This is acceptable for a dev tool.

The tool descriptions state the rule in their first sentence ("Always call find_categories first and ask the user…"), so any host model sees it.

### D6. Webapp `CategoryChoice`

A card inside the coach bubble:

- the title "No category for 'Veterinario' yet";
- one secondary button per similar category ("Use Mascotas · Estilo de vida");
- a divider;
- "Create 'Veterinario' in" with a shadcn `Select` of the groups (suggested one preselected) and a last item "New group…" that reveals a text field;
- the primary button "Create category".

After either choice, the card collapses to one line ("Using Mascotas" / "Created Veterinario in Estilo de vida", with Undo while allowed), and the follow-up `ActionPreview` renders below it. `ActionPreview` gains the multi-category body for `assignments`: rows for each category, To be assigned before → after, and Edit with one amount per row (as for moves).

### D7. Prompt and evals

`coach_v1.md` gains:

- **New categories:** never invent one; call `find_categories` first. If a similar category fits, propose using it; otherwise call `propose_category` with the best group and any similar-by-meaning categories, and let the widget ask.
- **Building a budget:** read `get_month` first, then propose day-to-day amounts with `propose_budget` within what's unassigned. Explain that categories with payments fill themselves.
- **Cash and other accounts:** pass the account the user mentions.

The prompt is still unshipped, so it stays `coach_v1` if this lands before release; otherwise it becomes `coach_v2`. Eval cases added:

- "gasté 15 en el veterinario" → `propose_category` with Mascotas among the similar;
- "pon 300 en el súper, 80 en gasolina y 50 en ocio" → one `assignments` action;
- "pagué 12 en efectivo en el bar" → a transaction in the cash account;
- "crea una categoría Super" → no new category, "Supermercado" offered.

## Risks / Trade-offs

- **[False positives: "Seguro coche" vs "Seguro hogar" are different things]** → They're only offered; "Create" is one tap away, and the reason is shown.
- **[False negatives by meaning: "Veterinario" vs "Mascotas"]** → The model's `similar` hint, plus the eval case. The server never relies on it alone to allow creation; it only adds options.
- **[MCP `set_budget` partial write on an API failure]** → Validate names first; the result lists exactly what was set; dev-only tool.
- **[Category undo leaves archived clutter]** → Archive is the only retire path by spec; the undo window is short in practice (before anything uses it).
- **[A long similar list overwhelms a beginner]** → Capped at 5, strongest first.

## Migration Plan

No schema change: `coach_actions.kind` and `status` are strings, so `category`, `assignments` and `resolved` fit. Deploy the backend and webapp together after `coach-conversation-actions`. Rollback: revert; existing `category` actions become inert (unknown kinds render nothing).

## Open Questions

- **Payment schedules from the chat:** decided: the next change, `coach-payments-setup`, which builds on this one. `for` follow-ups must stay open to a `payment` command.
- Should "Use X" also remember the choice for that payee (so the next "veterinario" goes straight to Mascotas)? Payee → last category already does this after the first transaction.
