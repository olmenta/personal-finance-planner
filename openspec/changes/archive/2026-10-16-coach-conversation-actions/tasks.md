## 1. Data model

- [x] 1.1 Add `CoachConversation`, `CoachMessage` (with the unique `(user_id, client_message_id)` partial index) and `CoachAction` to `models.py` (D1).
- [x] 1.2 Alembic revision creating the three tables, after `f1a2b3c4d5e6`.

## 2. Shared money operations

- [x] 2.1 Extract `budget_moves.apply_move` and `budget_view.set_assignment` from `routers/budget.py`. Make the router use them with unchanged behavior; the existing budget tests stay green (D6).
- [x] 2.2 Expose the transaction creation used by `POST /transactions` as a service function (if not already one) for the coach.

## 3. LLM layer

- [x] 3.1 `run_with_tools(route, output_type, messages, tools, deps, usage, conversation_id)` in `app/llm/agents.py`: same model resolution, overrides, settings, instructions caching and usage recording as `run_structured`.
- [x] 3.2 The `coach` route in `routes.py`.
- [x] 3.3 `app/llm/fakes.py`: a deterministic `fake:e2e` model for e2e, refused in production (D10).
- [x] 3.4 Tests: a tool-calling run through `override_route` records one usage row; `fake:` is refused in production.

## 4. Coach tools and actions

- [x] 4.1 `services/coach_tools.py`:
  - `CoachDeps`;
  - name resolution (case-insensitive, with close-name errors);
  - the read-only tools (`get_month`, `get_breakdown`, `get_category`, `get_future_payments`, `get_income`, `get_debts`, `search_transactions`);
  - the proposing tools (`propose_transaction`, `propose_assignment`, `propose_moves`), which store actions with their previews and register refs (D4).
- [x] 4.2 `services/coach_actions.py`:
  - `preview` and `revision` (D5);
  - `commit` (stale check, idempotency key, month row lock, atomic apply through the shared operations, recorded result);
  - `cancel`;
  - `undo` (after-value check, inverse, status) (D7, D8).
- [x] 4.3 The widget builders from refs: `month_summary`, `breakdown`, `future_payment`, `action_preview`, `action_result`, `coach_proposal`, `transaction`. Each carries `schema_version`, `snapshot_version` and `computed_at`, and unknown types are dropped (D3).

## 5. Conversation service and API

- [x] 5.1 `prompts/coach_v1.md`: role, language, tone, tool use, data-as-data rule, limits (D9).
- [x] 5.2 `services/coach_chat.py`:
  - get or create the conversation;
  - history pages;
  - `send` (idempotent by `client_message_id`, history window, snapshot context, run, build widgets, store the reply; 503 `coach_unavailable` after one retry or the 30 s timeout).
- [x] 5.3 `routers/coach_chat.py`:
  - `GET /coach/conversation`;
  - `POST /coach/messages`;
  - `GET /coach/actions`;
  - `POST /coach/actions/{id}/commit`;
  - `POST /coach/actions/{id}/cancel`;
  - `POST /coach/actions/{id}/undo`.

  Register it in `main.py`.
- [x] 5.4 Tests (model overridden):
  - history survives and paginates;
  - a double send stores one pair;
  - provider down → 503 keeps the user message, and a resend makes one reply;
  - the "how much to save" reply carries a `future_payment` whose numbers come from the engine (80,00 €, 5 contributions);
  - "gasté 40 en Mercadona" → `action_preview`, and no transaction until commit;
  - injected instructions in a description cause no proposal;
  - cover two categories → To Be Assigned and categories as specified, accounts unchanged;
  - a double commit applies once;
  - a write between preview and commit → 409 `action_stale`;
  - insufficient To Be Assigned → rejected with nothing applied;
  - cancel writes nothing;
  - undo right after restores, and undo after a change → 409;
  - History lists the actions;
  - an assignment on a category with payments is refused through the shared guard.

## 6. Evals

- [x] 6.1 `evals/coach.py`: cases for intent → tool (question, record expense, cover categories), no invented amounts (the reply's euro amounts ⊂ tool outputs), no humor for a shortfall, injected text ignored, Spanish replies. Add it to `evals/__main__.py` and the README table. Running it is the user's step (live calls), and it's required before shipping.

## 7. Webapp

- [x] 7.1 BFF routes for the conversation, messages and actions. `lib/api.ts` types for the message, widget union and action, plus their functions. Query keys and invalidation.
- [x] 7.2 `components/chat/`:
  - `ConversationView` (history with date separators, older pages on scroll up, the snapshot message last);
  - `UserBubble` and `CoachBubble`;
  - `SnapshotMessage` (deterministic sentences from `/home`, "View how it's split" breakdown, priority `ProposalCard`, "N more suggestions" with the groups);
  - `WidgetRenderer`, `FuturePaymentCard` (as in the mockup: icon, name, due month, saved of target with a percentage bar, current plan → needed, contributions, "Review adjustment" / "See other options", "Reviewing doesn't change your budget"), `ActionPreview` (before/after, accounts unchanged, Confirm / Edit / Cancel, "Needs updating" when stale), `ActionResult` (Undo);
  - `Composer` ("+" opens `AddTransactionDialog`; the field "Ask or record an expense…"; send; "Your history is kept"; the draft persisted);
  - `HistorySheet`;
  - progress while answering; a "coach can't answer right now" notice with retry on 503.
- [x] 7.3 Home page: header "Home" / "Your conversation with Olmenta" plus the History button; `ConversationView` replaces the delivery-2 widget stack (its widgets are reused inside the snapshot message); restore the scroll position.
- [x] 7.4 Sidebar matching the mockup: the five destinations, Settings and the user card, with no "Olmenta Pro" capsule.

## 8. Docs

- [x] 8.1 Update the end-user guides. `docs/user-guide.md`:
  - the Home section rewritten as the conversation;
  - a new "Talking to your coach" section (asking, recording an expense, reviewing and confirming a change, "Needs updating", undo, History, when the coach can't answer);
  - the coach section aligned.

  Check `docs/debt-guide.md` for Home wording.
- [x] 8.2 Check that the deltas match the implementation: `coach-conversation` added; `home`, `llm-layer` and `bff-proxy` modified.

## 9. Verification

- [x] 9.1 `uv run pytest` green in `backend/`.
- [x] 9.2 Type check, lint and build green in `webapp/`.
- [x] 9.3 e2e with `LLM_ROUTE_COACH_MODEL=fake:e2e` in the Playwright API env:
  - update `home.spec.ts` (conversation layout, the snapshot message, the breakdown link) and the specs that assert Home widgets (`category-targets`, `coach`, `income`, `debts`);
  - add `e2e/conversation.spec.ts`: ask how much to save → the `future_payment` card; "gasté 40 en Mercadona" → preview → confirm → result → undo; cover two categories in one confirmation; stale preview → "Needs updating"; the draft kept after navigating; History lists actions;
  - `volta run npm run e2e` green.
