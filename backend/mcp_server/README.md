# mcp_server — Olmenta dev MCP server

A local, stdio-only MCP server that exposes 12 curated Olmenta tools over the local REST API, so the developer can run their own budget from Claude Code, Claude Desktop or ChatGPT (through OpenAI's Secure MCP Tunnel).

- **Run:** `uv run python -m mcp_server` (the API must be running on `:8000`; override with `OLMENTA_API_URL`, loopback only)
- **Setup for each host, example prompts, data-flow note, troubleshooting:** [docs/dev-mcp-server.md](../../docs/dev-mcp-server.md)
- **Tool-call log (local, gitignored):** `.logs/calls.jsonl`
- **Design and spec:** `openspec/changes/dev-mcp-server/`

| Module | Role |
|---|---|
| `tools.py` | `ToolSpec`s: name, description, Pydantic args, `run(client, args)`. MCP-agnostic, so the future coach can reuse them |
| `server.py` | MCP adapter (`MCPServer`, mcp 2.x) + local call log |
| `client.py` | Thin HTTP client over the REST API; error codes → actionable messages; loopback check |
| `resolve.py` | Names → ids (exact, else single partial match, else candidates) |
| `money.py` | Euros in, cents inside, es-ES out; current month (Europe/Madrid) |
