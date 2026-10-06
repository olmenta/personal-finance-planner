# Design — Dev MCP Server

## Context

- **The API.** The backend API runs locally on `:8000` (the developer starts it by hand) and resolves every request to the seeded dev user (`deps.current_user`). Auth0 comes later.
- **The endpoints the tools need already exist:**
  - `GET /budget/{month}`, `PUT /budget/{month}/assignments/{id}`, `POST /budget/{month}/moves`;
  - `GET /overview/{month}`;
  - `GET|POST /transactions`;
  - `POST /transactions/review` and `/review/apply`;
  - `GET|POST /categories`, `GET|POST /accounts`, `POST /transfers`.
- **What this step serves.** It is step ① of the chat-first plan (explore, 2026-10-06): dogfood a tool set, learn the conversations, then build the in-app coach (③) on the same tool specs.

## Goals / Non-Goals

**Goals:**

- The developer can run their real budget from Claude Desktop or Claude Code, covering:
  - asking about the month;
  - adding expenses;
  - assigning and moving money;
  - categorizing and resolving uncategorized transactions (including transfers and matches).
- Tool specs designed so the in-app coach can reuse them.
- Zero new business logic: the API stays the single source of truth.

**Non-Goals:**

- Remote transport, OAuth, multi-user, deployment.
- LLM calls inside the server.
- Statement imports through MCP.
- Production-grade observability (tool calls are logged locally only).

## Decisions

### D1: A thin HTTP client, not in-process services

**Choice:** tools call the REST API with `httpx` against `OLMENTA_API_URL` (default `http://127.0.0.1:8000`).

**Why:**

- The API already encodes every rule (budget math, transfer invariants, review semantics) and is tested.
- Calling it keeps the server free of SQLAlchemy sessions, and exercises the same contract the webapp uses.

**Alternatives rejected:**

- Importing the services directly: it duplicates transaction and session handling, and couples the server to the database.
- Auto-generating tools from the FastAPI routes (e.g. fastapi-mcp): that yields one tool per route with route-shaped arguments (ids, cents), which models use badly.

### D2: Tool specs separate from execution

**How a tool is declared:** each tool is `ToolSpec(name, description, Args: BaseModel, run(args, ctx) -> str)`. `ctx` holds an `OlmentaClient` interface with high-level calls such as `budget(month)` and `add_transaction(...)`. In this change it is implemented over HTTP.

**Why it matters later:** the in-app coach (step ③) can register the same specs with LiteLLM tool calling and an in-process client.

**Descriptions are part of the contract:**

- they say when to use the tool, the units and the defaults;
- they say what the tool must not do (e.g. "never invent a category name: call `list_categories` or ask").

### D3: Names in, readable summaries out

- **Names, not ids.** Arguments take names. A resolver matches them in order:
  1. an exact, case-insensitive name;
  2. otherwise, a single substring match;
  3. otherwise, an error listing up to 8 candidates.

  Resolved ids never appear in arguments the model writes, except where a name can't apply: transaction ids returned by `list_transactions` / `review_uncategorized` and passed back to `apply_review`.
- **Money in euros.** Amounts are euro numbers (`12.5`) or strings (`"12,50"`) in, converted to integer cents; they are rendered es-ES (`12,50 €`) out.
- **Compact, scannable text out.** Results are compact Markdown or text summaries: group/category lines with assigned/spent/available, transactions as `date · payee/note · amount · category · id`. Raw JSON is too costly in tokens and hard to scan.

### D4: The tool set (12)

| Tool | Kind | API |
|---|---|---|
| `get_budget(month?)` | read | `GET /budget/{month}` — To Be Assigned, income, per-category assigned/spent/available, uncategorized summary |
| `get_month_overview(month?)` | read | `GET /overview/{month}` — paid, to pay, left to spend, saved |
| `list_transactions(month?, account?, uncategorized_only?, limit?)` | read | `GET /transactions?month=` (+ client-side filters) |
| `list_categories()` | read | `GET /categories` (active, by group; system groups marked) |
| `list_accounts()` | read | `GET /accounts` (balances, credit card debt) |
| `review_uncategorized()` | read | `POST /transactions/review` — rows with AI suggestions and twin matches |
| `add_transaction(amount, kind, category?, payee?, note?, date?, account?)` | write | `POST /transactions` |
| `assign(category, amount, month?)` | write | `PUT /budget/{month}/assignments/{id}` |
| `move_money(amount, to_category, from_category?, month?)` | write | `POST /budget/{month}/moves` (omitting `from_category` draws from To Be Assigned) |
| `create_category(name, group)` | write | `POST /categories` |
| `create_transfer(amount, from_account, to_account, date?, note?)` | write | `POST /transfers` |
| `apply_review(items)` | write | `POST /transactions/review/apply` — one item per transaction id; each item sets one or more of: `category` (name, or "none"), `payee`, `note`, `transfer_to` (account name), `link_match` (bool) |

`month` defaults to the current month (Europe/Madrid).

### D5: Safety model

- **Writes are explicit tools.** The host's per-tool approval is the confirmation; the developer can allow reads always and approve writes one by one.
- **Bank descriptions are untrusted text.** They come from banks and merchants. Tool results put them in a clearly delimited field and never in instruction position. The server description tells the model to treat them as data. This mirrors the "model proposes, the user decides" rule of the future coach.
- **Base URL restricted.** The server refuses a non-loopback `OLMENTA_API_URL`, so it can't be pointed at a shared environment by accident.

### D7: Hosts — Claude locally, ChatGPT through OpenAI's Secure MCP Tunnel

- **Claude Code / Claude Desktop** launch the stdio server directly (`claude mcp add …`, or `claude_desktop_config.json`).
- **ChatGPT** can't launch local processes; it connects to MCP servers over the network. OpenAI's Secure MCP Tunnel bridges this without exposing anything:
  - `tunnel-client` runs locally;
  - it starts our stdio server with `--mcp-command`;
  - it keeps an outbound-only HTTPS connection to OpenAI;
  - in ChatGPT's developer mode, a custom MCP server with connection type "Tunnel" is selected by tunnel id.
- **The server itself is unchanged:** stdio only, no HTTP transport, no public listener, so the loopback-only rule (D5) still holds.

**Alternative rejected:** a streamable-HTTP transport behind ngrok or a Cloudflare tunnel. It needs a public URL in front of an unauthenticated API holding real financial data.

### D6: Errors and logs

- **API errors** (machine codes such as `category_required`, `insufficient_available`) are mapped to one-line explanations the model can act on, e.g. "To Be Assigned has only 30,00 €".
- **Connection refused** returns "The Olmenta API isn't running on :8000 — start it with `uv run uvicorn app.main:app --reload`."
- **Tool-call log:** each call (name, arguments, duration, ok/error) is appended to `backend/mcp_server/.logs/calls.jsonl` (gitignored). It is the raw material for the coach's eval cases, and it stays on the developer's machine.

## Risks / Trade-offs

- **[The host LLM sees the developer's financial data]** → Personal use by choice, stated in the README. Nothing is shared with other users. A production coach would run under Olmenta's own processing terms.
- **[Tool descriptions tuned for one host model behave differently in another]** → That is acceptable for dogfooding. The coach will be tuned and evaluated on its own models later.
- **[The API is not running]** → Every tool returns the explicit start instruction (D6).
- **[`review_uncategorized` spends a backend LLM call]** → It is only used on demand. The description says it runs the AI suggestions and may take seconds.

## Migration Plan

Additive: a new package and a dev dependency. Nothing to migrate or roll back beyond deleting the package.

## Open Questions

None blocking. The tool list is expected to change during the dogfooding week; record changes in this design.
