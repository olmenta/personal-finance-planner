## 1. Category matching

- [ ] 1.1 `services/category_matching.py`: `similar_categories`, `similar_groups` and `suggest_group`, following the spec rules: fold, `same_name`, `contains`, `shared_word` with Spanish stop words, and `close_spelling` (ratio ≥ 0.8). Rank by rule strength, at most 5, active categories and non-system groups only (D1).
- [ ] 1.2 `GET /categories/similar?name=&kind=` in the categories router, with schemas; 422 for a blank name. Register it before `/{id}` routes.
- [ ] 1.3 Tests: case and accents, plural or typo, shared word, unrelated names on the default tree, the group suggestion (from a similar category, from shared words, the fallback), and the endpoint.

## 2. Accounts by type

- [ ] 2.1 `services/names.py`: account resolution by name, then by type word ("efectivo"/"cash"/"metálico", "tarjeta"/"card"/"crédito", "banco"/"cuenta"/"bank"), picking the single active account of that type and listing them when there are several (D4). `propose_transaction` uses it.
- [ ] 2.2 Mirror the fallback in `mcp_server/resolve.py` for `_account_id`.

## 3. Coach tools and actions

- [ ] 3.1 `find_categories(name)` read tool: similar categories with group and reason, plus the suggested group; registers nothing as a widget.
- [ ] 3.2 `propose_budget(items)` and the `assignments` kind in `coach_actions`: `_touched`, `_apply` through `set_assignment` per item in one savepoint, a multi-category preview, undo restoring each item, and the title "Set 3 categories: Supermercado 300,00 €, …" (D3).
- [ ] 3.3 `propose_category(name, group?, similar?, for?)` and the `category` kind (D2):
  - the exact-match short circuit;
  - similar categories from the service plus the model's existing-only hints;
  - the groups list and the suggested group;
  - the `for` follow-up stored without a category.
- [ ] 3.4 `POST /coach/actions/{id}/resolve {category_id}` (status `resolved`, follow-up proposed) and commit for `category`:
  - `group_id` or `new_group_name`, with the group similarity check and same-name reuse;
  - the category created through the categories service;
  - the follow-up proposed;
  - the message's widgets extended with the follow-up.
  - Extend `CoachCommitIn` and the action out schema.
- [ ] 3.5 Undo for `category`: allowed only while unused (no transactions, no assignment above zero, no schedule); it archives the category, and the group when this action created it and it's empty.
- [ ] 3.6 The `category_choice` widget builder (and `action_preview` for `assignments`), registered refs, and live state in `with_live_actions`.
- [ ] 3.7 Tests:
  - veterinario → a choice with Mascotas, nothing created;
  - "Use Mascotas" → a follow-up preview in Mascotas;
  - create in the suggested group → category plus a follow-up preview;
  - create in a new group;
  - the exact name returns the existing category;
  - a stale choice after a category is created elsewhere;
  - category undo allowed and refused once used;
  - a budget of three categories applied and undone;
  - a category with payments refused in `propose_budget`;
  - a cash expense in "Efectivo";
  - two cash accounts → the error lists them.

## 4. Prompt, fake model and evals

- [ ] 4.1 `prompts/coach_v1.md` (or `coach_v2.md` if v1 shipped): the new-category rules, building a budget, cash and other accounts (D7).
- [ ] 4.2 `app/llm/fakes.py`: phrasings for e2e. "gasté N en el veterinario" → `find_categories` then `propose_category` with `for`; "pon N en X, M en Y" → `propose_budget`; "pagué N en efectivo en X" → `propose_transaction` with `account = "efectivo"`.
- [ ] 4.3 `evals/coach.py`: the four cases in D7 with evaluators (right tool, `category_choice` attached, similar includes Mascotas or Supermercado, one `assignments` action with the three items, cash account). Running it is the user's step and required before shipping.

## 5. MCP server

- [ ] 5.1 Client: `similar(name, kind)`, `create_group`. Tools:
  - `find_categories`;
  - `create_category` with an optional `group` and `confirmed_new`, covering exact-match / similar / missing-group results (D5);
  - `create_group` with `confirmed_new`;
  - `set_budget` (validate every name first, then sequential PUTs, and a result listing what was set).

  The rule goes in the first sentence of each description.
- [ ] 5.2 Tests in `test_mcp_server.py`:
  - a near duplicate is caught;
  - created after `confirmed_new`;
  - group missing → groups listed;
  - an exact match;
  - `create_group` similarity;
  - `set_budget`, with a bad name writing nothing;
  - a cash account by type.
- [ ] 5.3 `docs/dev-mcp-server.md`: the new tools and the confirm-before-create rule.

## 6. Webapp

- [ ] 6.1 BFF route `api/coach/actions/[id]/resolve`. `lib/api.ts`: the `category_choice` widget type, the `assignments` preview, `resolveCategoryChoice`, and the commit with `group_id` / `new_group_name`.
- [ ] 6.2 `components/chat/CategoryChoice.tsx` (D6):
  - "Use X · Group" buttons;
  - "Create 'name' in" with a group `Select` (suggested preselected), "New group…" with a text field, and "Create category";
  - after the choice, a one-line summary (with Undo while allowed) and the follow-up `ActionPreview` below.
  - Add it to `WidgetRenderer`.
- [ ] 6.3 `ActionPreview`: the `assignments` body (rows per category, To be assigned) and Edit with one amount per row.

## 7. Docs

- [ ] 7.1 Update the end-user guides. In `docs/user-guide.md` ("Talking to your coach"):
  - building your budget with the coach;
  - recording in cash or another account;
  - new categories (similar ones first, choosing the group, a new group, undo).

  Check `docs/debt-guide.md` for anything about categories created from the chat.
- [ ] 7.2 Check that the deltas match the implementation: `category-matching` added; `coach-conversation`, `dev-mcp-server`, `categories-api` and `bff-proxy` modified.

## 8. Verification

- [ ] 8.1 `uv run pytest` green in `backend/`.
- [ ] 8.2 Type check, lint and build green in `webapp/` (separate dist dir).
- [ ] 8.3 e2e (`fake:e2e`). Add to `e2e/conversation.spec.ts` (or a new `budget-setup.spec.ts`):
  - veterinario → choice → "Use Mascotas" → preview → confirm;
  - veterinario → create in a picked group → the category appears in Budget;
  - "New group…";
  - a three-category budget in one confirmation;
  - a cash expense lands in Efectivo.

  `volta run npm run e2e` green.
