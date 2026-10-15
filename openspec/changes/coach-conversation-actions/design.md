## Context

**Redesign v2, delivery 3:** "general chat persistence, typed tools, preview/version/commit/replay, validated grouped moves, controlled undo. Reuse import and onboarding patterns." The approved mockup (`ui-experiments/redesign.png`) shows Home as a conversation. Each piece maps to a widget or element here:

| Mockup element | Here |
|---|---|
| Refreshed month as a coach message ("View how it's split") | Snapshot message |
| User question bubble | User message |
| Insurance card (saved/target, current plan → needed, contributions, "Review adjustment", "Reviewing doesn't change your budget") | `future_payment` widget |
| Composer with "+" | Composer |
| History button | History |

**What exists:**

- `app/llm.run_structured`: single structured calls, with usage recorded and Logfire configured; no tools.
- The onboarding service: persisted transcript, versioned prompt, per-turn validation.
- The dev MCP server: 12 tools with good conventions (names over ids, euros), calling the REST API.
- `services/budget_moves.validate_source`.
- The assignment and move logic, inline in `routers/budget.py`.
- `POST /transactions`.
- Home's snapshot (`build_home`) and rule-based coach proposals with revision binding.

## Goals / Non-Goals

**Goals:**

- A persistent, resumable conversation, with no duplicate messages or actions on retries.
- A coach that answers from real numbers through tools, and can only *propose* changes.
- Every change goes through preview → confirm → atomic apply → recorded result → validated undo.
- A deterministic Home that keeps working when the AI doesn't.

**Non-Goals:**

- Proactive messages or notifications (`coach-proactivity`).
- Funded/wanted detectors, locale and tone variants (`future-coaching`).
- Editing schedules, income or debts from chat. The coach links to their editors.
- Streaming replies (a progress line is enough for v1).
- Voice, attachments, and an immutable ledger.
- Feature flags (single dev user; same reason as delivery 2).

## Decisions

### D1. Data model

**`coach_conversations`:** `id`, `user_id` (unique), `created_at`, `updated_at`.

**`coach_messages`:**

- `id`, `conversation_id`, `role`, `text`, `widgets` (JSONB);
- `client_message_id` (unique with `user_id`, user messages only);
- `reply_to` (assistant → user message);
- `snapshot_version`, `created_at`.

**`coach_actions`:**

- `id`, `user_id`, `message_id`, `kind` (`transaction` | `assignment` | `moves`);
- `command` (JSONB, typed params);
- `preview` (JSONB: before/after per category, To Be Assigned before/after);
- `revision`, `status`;
- `idempotency_key` (unique per action when set);
- `result` (JSONB: ids created, after values), `applied_at`, `undone_at`, `created_at`.

These are additive tables. `BudgetAssignment` and `Transaction` stay the source of truth (redesign §8: "do not replace BudgetAssignment with a new ledger").

### D2. `run_with_tools` in the LLM layer

`app/llm/agents.py::run_with_tools(route, output_type, messages, tools, deps, usage, conversation_id)` builds a Pydantic AI `Agent` with `tools=[Tool(fn) ...]`, `deps_type`, and the same model, settings, instructions caching and override hooks as `run_structured`. It records one `llm_usage` row per run.

The tools are plain functions taking `RunContext[CoachDeps]` (db session, user, conversation, a collector for proposed actions and widget refs). The route `coach` uses `anthropic:claude-sonnet-5`, with `max_tokens` 4000.

### D3. The model never produces an amount

The output type is `CoachReply {text: str, widgets: list[WidgetRef]}`, with `WidgetRef {type, ref}`. Refs point to objects the tools produced in this run:

- `action:<id>`;
- `future_payment:<category_id>`;
- `proposal:<fingerprint>`;
- `transaction:<id>`;
- `month`;
- `breakdown`.

The server builds each widget from the engine at the end of the run, drops unknown types and refs, and stores them on the message. The prompt tells the model to quote only numbers returned by tools. The eval suite checks the reply text against the tool outputs.

### D4. Tool catalog

Tools return compact JSON with names and euros as strings formatted es-ES, plus ids for refs.

**Read-only:**

| Tool | Built on |
|---|---|
| `get_month` | `build_home` summary, status, reasons |
| `get_breakdown` | the same summary |
| `get_category(name)` | budget view row plus schedules |
| `get_future_payments(name?)` | per scheduled category: next due month, target (payments until then), saved (available), normal, catch-up/needed, contributions left (inclusive months until due) |
| `get_income(month?)` | `month_income` |
| `get_debts` | `build_debts_view` |
| `search_transactions(text?, month?, category?)` | up to 20 rows |

**Proposing:**

| Tool | Behavior |
|---|---|
| `propose_transaction(amount, kind, category?, payee?, date?, account?)` | Category defaults to the payee's last-used category |
| `propose_assignment(category, amount)` | Day-to-day categories only; others get a validation error in the tool result, so the model explains it |
| `propose_moves([{from|unassigned, to, amount}])` | One or more moves |

Name resolution follows the MCP server's conventions: case-insensitive, with an error listing close names.

### D5. Preview and revision

`services/coach_actions.preview(db, user, command)` reads the current month's budget view and returns:

- **for assignment and moves:** each affected category's assigned and available before and after, To Be Assigned before and after, and the note `accounts_unchanged`;
- **for a transaction:** the transaction fields plus the category's available and To Be Assigned after.

`revision = sha256(canonical json(preview))[:16]`. Commit recomputes the preview: a different revision returns 409 `action_stale` with the new preview, and the old action's status becomes `stale`.

### D6. One implementation for forms and coach

The budget router's logic moves into services, and the router keeps calling them with unchanged behavior:

- `services/budget_moves.apply_move(db, user, month, from, to, amount)`, which validates through `validate_source` or the To Be Assigned bound;
- `services/budget_view.set_assignment(db, user, month, category, amount)`, which keeps the `assignment_from_payments` guard.

Transactions are created through the service behind `POST /transactions`. A grouped move runs inside one savepoint: any failure rolls the whole group back. Commits happen in the request transaction, as with every other write.

### D7. Idempotency

- **Send:** `(user_id, client_message_id)` is unique. A resend returns the stored pair; a resend after a failed reply reuses the user message.
- **Commit:** stores `idempotency_key` and the `result`. A repeated commit with the same key returns the result. The client generates the key once per confirm intent.

Concurrent different commits touching the same money are serialized by the stale check, plus a `SELECT … FOR UPDATE` on the user's `budget_months` row for the month during apply. That's the shared mutation boundary the redesign asks for.

### D8. Undo

An applied action stores the after values: each affected assignment, or the created transaction's id and its fields. Undo checks that the current values equal them, then applies the inverse with the same services. On a mismatch it returns 409 `undo_not_possible`. Status becomes `undone`; nothing is deleted except the transaction an undone record created.

### D9. Prompt, history and safety

`prompts/coach_v1.md` is the versioned prompt, like onboarding. It covers:

- the role: calm, plain language, second person, the user's language;
- tone: no humor for shortfalls, illness, unemployment or distress;
- tool use: always read before stating numbers, propose rather than claim changes, explain what a preview does;
- refusal to treat tool data as instructions;
- what the coach can't do (edit schedules, income or debts: it links to them).

Each run sends the last 20 messages plus a short snapshot context from `build_home`. Content goes to Logfire only outside production with the content flag, per the existing policy. `llm_usage` holds no content.

### D10. Testing without live calls

- **Backend tests:** `override_route("coach", FunctionModel(...))` scripts the tool calls.
- **E2E:** the API runs with `LLM_ROUTE_COACH_MODEL=fake:e2e`, which `_model` resolves to a deterministic `FunctionModel` in `app/llm/fakes.py`. It maps a few phrasings to tool calls ("gasté N en X" → `propose_transaction`; "cuánto … guardar" → `get_future_payments`; "cubre" → `propose_moves`). It's refused when the environment is production.
- **The live model:** covered by `evals/coach.py`, which the user runs, as with onboarding.

### D11. Webapp

- **`components/chat/`:**
  - `ConversationView`: history with date separators, plus the snapshot message last;
  - `CoachBubble` and `UserBubble`;
  - `SnapshotMessage`: deterministic sentences from `/home`, "View how it's split" with the breakdown, the priority `ProposalCard`, and "N more suggestions" with the groups;
  - `WidgetRenderer`, `FuturePaymentCard`, `ActionPreview` (Confirm / Edit / Cancel), `ActionResult` (Undo);
  - `Composer` ("+" opens `AddTransactionDialog`);
  - `HistorySheet`.
- **Draft and scroll:** the draft goes to `localStorage` (try/catch) and the scroll position to `sessionStorage`.
- **Reviewing from a widget, and Edit:** `POST /coach/actions` stores a new proposal from a typed command (ids) and applies nothing. "Review adjustment" on a `future_payment` previews a move of the missing amount from To Be Assigned; Edit sends the changed amounts with `replaces`, and the message's preview points to the new action.
- **Server state:** TanStack keys `["coach-conversation"]` and `["coach-actions"]`. A commit or undo invalidates the money queries plus these.
- **Home page:** becomes `ConversationView`. The delivery-2 widgets are reused inside the snapshot message.
- **Sidebar:** matches the mockup, without the "Olmenta Pro" capsule.

### D12. Language

Deterministic UI copy stays English placeholder until next-intl (project rule). The coach replies in the user's language (Spanish for the launch). The mockup's Spanish chrome arrives with next-intl in `future-coaching`.

## Risks / Trade-offs

- **[The model states a number not from a tool]** → Widgets carry the authoritative numbers, and the prompt plus evals check the text. A post-check that flags euro amounts in the text absent from the tool outputs is logged (count only) for the evals.
- **[Latency of a tool-using run is several seconds]** → A progress line, forms always available, a 30 s timeout per model request and at most 8 requests per run, then `coach_unavailable`.
- **[Cost]** → One run per message, with prompt caching on the instructions and usage recorded per run.
- **[Grouped moves partially valid]** → All-or-nothing in a savepoint, and the coach explains the rejection.
- **[Concurrency between form and chat]** → The stale check plus the month row lock. A test runs a form write between preview and commit.
- **[The fake model drifts from real behavior]** → It only drives e2e plumbing. Behavior quality is the eval suite's job.

## Migration Plan

1. The Alembic revision creates the three tables (no data step).
2. Deploy the backend and webapp together after `redesign-home-navigation`.
3. Rollback: hide the composer (revert the webapp). The tables are inert without it.

## Open Questions

- The exact snapshot sentences in Spanish come with next-intl and the `future-coaching` tone work.
- Whether History should also list rule-based proposal acceptances. Not in v1; their state lives in `coach_proposal_states`.
