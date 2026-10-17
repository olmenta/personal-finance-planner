## Why

The Home chat can answer questions, record an expense in a known category, and move money, but it can't help someone **build** their budget: it can't create a category or a group, and it sets amounts one category at a time. Someone who has never budgeted asks things like "ayúdame a armar mi presupuesto" or "gasté 15 en el veterinario" (with no pets category yet), and today the chat has to send them to the Budget screen. The dev MCP server has the same gap, and its `create_category` is worse: it creates a category without checking whether a similar one already exists, so duplicates like "Super" next to "Supermercado" appear.

Duplicate categories quietly break a zero-based budget: money and spending split across two places, and the person stops trusting the numbers. So creating a category must always start by finding the similar ones and asking.

## What Changes

- **New: similar categories first, everywhere.**
  - One backend service finds categories similar to a name: the same name with different case or accents, one name contained in the other, shared words, close spelling. The chat and the MCP server both use it, through `GET /categories/similar?name=`.
  - Before creating a category, the chat and the MCP server SHALL look for similar ones and ask the user whether to use one of them or create the new one. Nothing is created without that answer.
  - The model can add similar categories by meaning ("veterinario" ~ "Mascotas"), but it can only point to existing categories.
- **New: creating categories and groups from the chat.**
  - A `category_choice` widget lists the similar categories as "Use X" options and offers "Create 'Y'" with a **dropdown of the existing groups**. The suggested group is preselected, and "New group…" lets the user name one.
  - Choosing "Use X" or creating the category continues what the user was doing. For example, the pending expense is previewed in the chosen or new category, still waiting for Confirm.
  - Creating a group follows the same rule: look for similar groups first.
- **New: building the budget from the chat.**
  - The coach can propose several amounts at once ("pon 300 en el súper, 80 en gasolina y 50 en ocio"). They appear as one preview with before/after per category and To be assigned, and apply all or none.
  - Categories with payments keep their computed amounts: the coach explains that and offers a move instead.
- **Transactions in any account, e.g. cash.** "Pagué 12 en efectivo en el bar" records the expense in the user's cash account. Account names resolve as before, and "efectivo" / "cash" / "tarjeta" also match an account of that type when only one fits.
- **The dev MCP server follows the same rules.**
  - `create_category` returns the similar categories and refuses to create until it's called again with `confirmed_new = true`. The result lists the existing groups with the suggested one.
  - New tools: `find_categories` (similar names), `create_group` (same similarity rule), and `set_budget` (several assignments in one call).
- **Prompt.** The coach prompt gains the rules: look up similar categories before proposing a new one, and always let the user choose. It also covers how to help build a budget from scratch (start from what's unassigned, day-to-day categories first, explain that payments are computed). Changing the prompt requires an eval run.

## Capabilities

### New Capabilities

- `category-matching`: finding the categories and groups similar to a name, the suggested group for a new category, and `GET /categories/similar`.

### Modified Capabilities

- `coach-conversation`:
  - new tools (`find_categories`, `propose_category`, `propose_budget`);
  - the `category_choice` widget;
  - new action kinds (`category`, `assignments`) with the same preview/confirm/undo lifecycle;
  - transactions in any account by name or type.

  This depends on `coach-conversation-actions` being archived first.
- `dev-mcp-server`:
  - the curated tool set adds `find_categories`, `create_group` and `set_budget`;
  - `create_category` requires the similar-categories check and an explicit `confirmed_new`.
- `categories-api`: adds `GET /categories/similar`.
- `bff-proxy`: proxies the new action endpoints the widget needs.

## Impact

- **Backend:**
  - `services/category_matching.py`, plus the `GET /categories/similar` route;
  - coach tools and actions (`coach_tools.py`, `coach_actions.py`, `coach_widgets.py`), with the new kinds `category` and `assignments`, and a `resolve` endpoint for a category choice;
  - `prompts/coach_v1.md` rules;
  - the eval cases (`evals/coach.py`);
  - tests.
- **MCP server:** `mcp_server/tools.py` (create_category check, new tools), the client, and the tool descriptions; `docs/dev-mcp-server.md`.
- **Webapp:**
  - `components/chat/CategoryChoice.tsx` (similar options, the group dropdown, "New group…");
  - the multi-category preview in `ActionPreview`;
  - API types and BFF routes;
  - e2e.
- **Docs:** the "Talking to your coach" section of the user guide.
- **Unaffected:** budget math, payment schedules, imports, and the onboarding interview (which still creates the first tree).
