# Tasks — Dev MCP Server

## 1. Package and client

- [ ] 1.1 Add the `mcp` Python SDK as a dev dependency (`uv add --dev mcp`) and create `backend/mcp_server/` (`__main__.py`, `server.py`, `client.py`, `tools/`, `README.md`); gitignore `backend/mcp_server/.logs/`
- [ ] 1.2 `client.py`: `OlmentaClient` interface + HTTP implementation (`httpx`, `OLMENTA_API_URL`, loopback-only check at startup, connection-refused → start-the-API message, API error codes → one-line messages)
- [ ] 1.3 Resolvers: category / group / account by name (exact case-insensitive, then single partial match, else candidates error); euro parsing (number or es-ES string → cents) and es-ES formatting; current month in Europe/Madrid

## 2. Tools

- [ ] 2.1 `ToolSpec` (name, description, args model, run) and registration with the MCP server; per-call JSONL log
- [ ] 2.2 Reads: `get_budget`, `get_month_overview`, `list_transactions`, `list_categories`, `list_accounts`, `review_uncategorized` — compact text summaries, bank text delimited as data
- [ ] 2.3 Writes: `add_transaction`, `assign`, `move_money`, `create_category`, `create_transfer`, `apply_review`
- [ ] 2.4 Tool descriptions reviewed as a set: when to use, units, defaults, what not to do (never invent names, call `list_categories` or ask)

## 3. Tests and docs

- [ ] 3.1 Unit tests for resolvers, euro parsing/formatting, error mapping, and loopback check (no network)
- [ ] 3.2 Integration test: each tool against the FastAPI app via `httpx` transport (test DB), covering the spec scenarios
- [ ] 3.3 `docs/dev-mcp-server.md` (linked from `backend/mcp_server/README.md`): prerequisites (API running on :8000), registering with Claude Code (`claude mcp add …`) and Claude Desktop (config JSON), ChatGPT through OpenAI's Secure MCP Tunnel (`tunnel-client init/doctor/run` with `--mcp-command`, then developer mode → custom MCP server → Tunnel), example prompts, the data-flow note (personal use; financial data reaches the host's LLM provider), the call log location, troubleshooting

## 4. Verification

- [ ] 4.1 `uv run pytest` green in `backend/`
- [ ] 4.2 Manual: register in Claude Code, ask about the month, add an expense, move money, resolve an uncategorized row — then start the dogfooding week and record tool changes in `design.md`
