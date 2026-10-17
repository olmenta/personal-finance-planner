## Why

Delivery 3 of the conversational redesign (`ui-experiments/redesign.md` v2, §5, §8–§10). The approved mockup (`ui-experiments/redesign.png`) makes Home "your conversation with Olmenta":

- The refreshed month arrives as a coach message ("I've updated your month… View how it's split").
- The user asks in their own words ("How much would I need to save?").
- The answer comes with typed cards. In the mockup, the car insurance card shows 200 € saved of 600 €, current plan 50 €/month → 80 €/month to make it, "Review adjustment", and "Reviewing doesn't change your budget".
- The composer ("Ask or record an expense…") and a History keep everything.

Delivery 2 gave Home a deterministic snapshot. The safety baseline made actions exact and replay-safe. What's missing:

- a conversation that persists and resumes;
- a coach that understands intent and reads real numbers through typed tools;
- a safe lifecycle for any change it proposes: preview, confirm, apply once, undo.

## What Changes

- **New: one conversation per user, persisted.**
  - Messages (user and coach) store their text and typed widgets.
  - Home loads the history with date separators. It never adds a greeting as a stored message on each visit.
  - The month snapshot from `GET /home` is shown at the top as a coach message that isn't stored.
  - The draft and the scroll position survive leaving Home.
- **New: sending is idempotent.**
  - Each message carries a client id. Resending it after a network error or an AI outage never duplicates a message and retries only the reply.
  - When the AI is unavailable, Home keeps the snapshot and every form working, and says the coach can't answer right now.
- **New: the coach agent on the LLM layer.**
  - A `coach` route runs a Pydantic AI agent with a versioned prompt (`prompts/coach_v1.md`) and **typed tools**, in two groups:
    - **read-only tools:** month summary and breakdown, a category, future payments with saved/needed, income this month, debts, transaction search;
    - **proposing tools:** record a transaction, set a day-to-day assignment, move money (one or a group of moves).
  - **Tools never write money.** Proposing tools create a server-computed proposal.
  - **The model never produces an amount:** every number shown comes from the engine. The model writes the explanation and chooses which widgets to attach from a fixed catalog.
  - Transaction descriptions and payee names are untrusted data, never instructions.
- **New: typed widgets.** `month_summary`, `breakdown`, `future_payment` (the mockup's card), `action_preview`, `action_result`, `coach_proposal` and `transaction`. Each carries a `schema_version` and the `snapshot_version` it was computed from.
- **New: the action lifecycle.** Intent → deterministic proposal → visible before/after preview → user confirmation → version and source validation → atomic application → recorded result → optional validated undo:
  - **Commit:** requires the preview's `revision` and an idempotency key. A retry returns the recorded result.
  - **Stale preview:** if the numbers changed, the API returns 409 `action_stale` with a fresh preview, and the old one shows "Needs updating".
  - **Grouped moves:** they apply completely or not at all.
  - **Undo:** a validated inverse, offered only while nothing it touches has changed since. Otherwise the coach offers a new review.
  - **Shared validation:** moves go through the shared validator (`budget_moves`), and assignments respect "computed from payments".
- **New: History.** A header button lists applied actions, newest first, with their result and an undo when it's still valid.
- **Home becomes the conversation**, following the mockup:
  - title "Home", subtitle "Your conversation with Olmenta", and a History button;
  - date separators;
  - the snapshot coach message, with "View how it's split" (the exact breakdown), the priority action and a link to the other suggestions;
  - the message list with widgets;
  - the composer: "+" for the add-transaction form, the text field, send, and "Your history is kept".

  The delivery-2 widgets live on inside messages. The sidebar matches the mockup: the five destinations, Settings and the user card, with no "Pro" upsell.
- **Evals.** A `coach` eval suite (intent → correct tool, never invented amounts, tone without humor for shortfalls, untrusted text ignored). Running it is the user's step (live calls), and it's required before shipping per the LLM-layer rule.
- **Docs.** The user guide gets a "Talking to your coach" section (asking, recording expenses, reviewing and confirming changes, undo, history) and the updated Home description.

## Capabilities

### New Capabilities

- `coach-conversation`:
  - conversation and message persistence;
  - idempotent sending and the AI-unavailable path;
  - the coach agent with read-only and proposing tools on the `coach` route;
  - the widget catalog;
  - the action lifecycle (preview, revision, commit with idempotency, stale detection, atomic grouped moves, validated undo);
  - History;
  - the conversation screen on Home.

### Modified Capabilities

- `home`: the Home screen becomes the conversation layout from the mockup. The snapshot is shown as an unstored coach message with the breakdown and the priority action; the composer and History are added. It depends on `redesign-home-navigation` being archived first.
- `llm-layer`: the layer runs agents with typed tools (`run_with_tools`), and the `coach` route exists.
- `bff-proxy`: proxies the conversation, message and action routes.

## Impact

- **Backend:**
  - new tables `coach_conversations`, `coach_messages` and `coach_actions`, with an Alembic migration;
  - `app/llm/agents.py` (`run_with_tools`) and `routes.py` (`coach`);
  - `services/coach_chat.py` (history, sending, agent run);
  - `services/coach_tools.py` (read and propose tools, name resolution);
  - `services/coach_actions.py` (preview, commit, undo, built on the budget and transaction services);
  - `routers/coach_chat.py`;
  - `prompts/coach_v1.md`;
  - `evals/coach.py`;
  - tests with the model overridden (no live calls).
- **Webapp:**
  - the Home conversation (`components/chat/*`: message list, coach and user bubbles, widget renderer, action preview and result, composer, History sheet), plus `lib/api.ts` and BFF routes;
  - the sidebar matching the mockup;
  - e2e with the backend model overridden.
- **Depends on:** `redesign-home-navigation` (PR #4) being merged and archived before this change archives.
- **Unaffected:** budget math, the projection, coach rules, debts, income and imports. Rule-based coach proposals keep their endpoints and appear in the snapshot message.
