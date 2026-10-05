# Dev MCP Server

## Why

Olmenta is moving toward a chat-first experience, in which the coach handles onboarding, budget questions, adding transactions and coaching (explore session, 2026-10-06). Before building the in-app coach, we need to learn which conversations work, which tools the model needs, and where a visual card beats text. The cheapest way to learn that is for the developer to run their own budget from an LLM client they already use, such as Claude Desktop or Claude Code, through a curated set of Olmenta tools for a week. That gives us real conversations that become the coach's spec and the first tool-use eval cases.

## What Changes

- **A local MCP server for the developer.** It exposes a small, curated set of Olmenta domain tools to an MCP host over stdio:
  - Claude Desktop and Claude Code launch it directly;
  - ChatGPT reaches the same stdio server through OpenAI's Secure MCP Tunnel (`tunnel-client`, outbound-only, no public listener).
- **The tools:**
  - **Reads:** budget month, month overview, transactions, categories, accounts, and the review of uncategorized transactions.
  - **Writes:** add a transaction, assign, move money, create a category, create a transfer, and apply review decisions.
- **A thin client over the existing REST API.** Every tool calls the backend's HTTP API (`localhost:8000`, the dev user). There is no second copy of business rules and no direct database access.
- **LLM-friendly contracts.**
  - Categories, accounts and groups are given **by name**, and the server resolves them to ids. An ambiguous or unknown name returns the candidates so the model can ask.
  - Amounts go in and out in **euros**; cents stay internal.
  - Dates are ISO dates, defaulting to today.
  - Results are compact, readable summaries, not raw API payloads.
- **Tool definitions shaped for reuse.** Each tool is a declared spec (name, description, argument model) separate from how it executes. The future in-app coach can reuse the same specs with an in-process executor instead of HTTP.
- **Dev-only by construction.**
  - It only talks to a localhost backend.
  - There is no auth, no remote transport, and it is not deployed.
  - Write confirmations rely on the MCP host's per-tool approval prompts.

## Capabilities

### New Capabilities

- `dev-mcp-server`: the local MCP server contract. It covers the tool set and its argument and result conventions (names over ids, euros, dates), name resolution and errors, the HTTP-only execution against a local backend, and the dev-only constraints.

### Modified Capabilities

None. The REST API is used as it is.

## Impact

- **Backend repository:** a new package, `backend/mcp_server/`, that reuses the backend's uv environment and `httpx`.
  - Adds the `mcp` Python SDK as a dev dependency.
  - Runs with `uv run python -m mcp_server`.
- **Docs:** `docs/dev-mcp-server.md` explains how to use it locally with Claude Code, Claude Desktop and ChatGPT (developer mode + Secure MCP Tunnel), and what data reaches each host's LLM provider.
- **No change** to the API, the webapp or the database.
- **Data:** the developer's own financial data flows to the MCP host's LLM provider. This is the developer's choice, for personal use, and the README states it. Nothing here is offered to other users.
- **Out of scope:**
  - remote MCP and OAuth;
  - multi-user;
  - the in-app coach agent;
  - imports through MCP (files stay in the webapp);
  - LLM calls inside the MCP server (the host model does the reasoning).
