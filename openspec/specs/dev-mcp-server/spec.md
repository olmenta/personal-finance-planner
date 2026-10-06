# dev-mcp-server Specification

## Purpose

The local, dev-only MCP server that lets the user run their own budget from Claude or ChatGPT: the tool set and its argument and result conventions (names over ids, euros, dates), name resolution and errors, HTTP-only execution against a local backend, and the dev-only constraints.

## Requirements

### Requirement: Local MCP server over the Olmenta API

The repository SHALL provide an MCP server, runnable with `uv run python -m mcp_server` from `backend/`, that exposes Olmenta domain tools to an MCP host over stdio. Every tool SHALL execute through the backend's REST API at `OLMENTA_API_URL` (default `http://127.0.0.1:8000`) and SHALL NOT access the database directly or call an LLM itself. The server SHALL refuse to start when `OLMENTA_API_URL` does not point to a loopback address, and SHALL provide no remote transport and no authentication — it is a developer tool, not a user-facing surface.

#### Scenario: Registered in Claude Code

- **WHEN** the developer registers the server with their MCP host following the README and the API is running
- **THEN** the host lists the Olmenta tools and a call to `get_budget` returns the current month's budget

#### Scenario: Non-local API refused

- **WHEN** `OLMENTA_API_URL` is set to `https://api.example.com`
- **THEN** the server exits at startup explaining that it only talks to a local backend

#### Scenario: API not running

- **WHEN** a tool is called while nothing listens on the API URL
- **THEN** the tool returns an error telling the developer to start the API with `uv run uvicorn app.main:app --reload`

### Requirement: Curated tool set

The server SHALL expose exactly these tools: reads `get_budget`, `get_month_overview`, `list_transactions`, `list_categories`, `list_accounts`, `review_uncategorized`; writes `add_transaction`, `assign`, `move_money`, `create_category`, `create_transfer`, `apply_review`. Each tool SHALL carry a description stating when to use it, its units and defaults, and what it must not do. Write tools SHALL perform exactly the API write they describe and nothing else.

#### Scenario: Expense added from a sentence

- **WHEN** the developer says "gasté 40 en Mercadona" and the host calls `add_transaction` with `amount = 40`, `kind = "expense"`, `category = "Supermercado"`, `payee = "Mercadona"`
- **THEN** a −40,00 € confirmed transaction exists in Supermercado for today in the main account, and the tool result states it

#### Scenario: Money moved from To Be Assigned

- **WHEN** `move_money` is called with `amount = 50` and `to_category = "Restaurantes"` and no `from_category`
- **THEN** 50,00 € move from To Be Assigned to Restaurantes in the current month

#### Scenario: Uncategorized transactions resolved

- **WHEN** `review_uncategorized` lists a row and `apply_review` is called for its id with `category = "Supermercado"` and `note = "Compra semanal"`
- **THEN** the transaction is categorized with that note, with the same semantics as the webapp's review

### Requirement: LLM-friendly arguments and results

Tool arguments SHALL take categories, groups and accounts by name, resolved case-insensitively — an exact name first, else a single partial match — and an unknown or ambiguous name SHALL return an error listing the candidates instead of guessing. Amounts SHALL be accepted in euros (number or es-ES string) and converted to integer cents; results SHALL render money in es-ES format. Month arguments SHALL default to the current month in Europe/Madrid and dates to today. Results SHALL be compact text summaries, not raw API payloads, and API error codes SHALL be translated into one-line actionable messages. Text that originates from bank statements (descriptions, payees) SHALL be presented as clearly delimited data.

#### Scenario: Ambiguous category name

- **WHEN** `assign` is called with `category = "trans"` and the user has "Transporte público" and "Transferencias"
- **THEN** nothing is written and the result lists both names so the model can ask which one

#### Scenario: Euro amounts

- **WHEN** `add_transaction` is called with `amount = "12,49"`
- **THEN** the stored amount is 1249 cents and the result reads "12,49 €"

#### Scenario: Readable API error

- **WHEN** `move_money` fails with `insufficient_to_be_assigned`
- **THEN** the result explains that To Be Assigned doesn't hold that much and states how much it holds

### Requirement: Reusable tool specs and local call log

Each tool SHALL be declared as a spec (name, description, argument model) separate from its executor, so the same specs can later run in-process for the in-app coach. Every tool call SHALL be appended (tool name, arguments, duration, ok/error) to a gitignored local JSONL log for building evaluation cases; the log SHALL never leave the developer's machine.

#### Scenario: Call logged locally

- **WHEN** the host calls `get_budget`
- **THEN** one line with the tool name, its arguments, the duration and the outcome is appended to the local log, and the file is ignored by git
