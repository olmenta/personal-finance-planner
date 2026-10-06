# Olmenta dev MCP server: use your budget from Claude or ChatGPT

A local MCP server that lets you run **your own** Olmenta budget from an AI chat. You can:

- ask how the month is going;
- add expenses ("gasté 40 en Mercadona");
- assign and move money;
- resolve uncategorized transactions (category, note, transfer, matching transfer).

It is a developer tool for dogfooding the future in-app coach (openspec change `dev-mcp-server`). It is not a user feature.

```
 Claude Code / Claude Desktop ──stdio──┐
                                       ├──► python -m mcp_server ──HTTP──► Olmenta API :8000 ──► your DB
 ChatGPT ──OpenAI Secure MCP Tunnel────┘     (12 tools, thin client)        (dev user)
          (outbound-only, no public URL)
```

## What happens to your data

- **Your financial data goes to the chat provider's model.** Whatever a tool returns (balances, categories, amounts, bank descriptions, notes) is sent to the LLM of the host you use: Anthropic for Claude, OpenAI for ChatGPT. Use it only with your own data.
- **The server only talks to a local API.** It refuses to start if `OLMENTA_API_URL` isn't localhost. It has no network listener of its own.
- **Every tool call is logged locally** to `backend/mcp_server/.logs/calls.jsonl` (gitignored): tool, arguments, duration and outcome. That log is the raw material for the coach's eval cases. It stays on your machine. Delete it whenever you like.

## Before you start (every host)

1. Install the dependencies once, in `backend/`:

   ```bash
   uv sync
   ```

2. Start the API and leave it running:

   ```bash
   cd backend
   uv run uvicorn app.main:app --reload
   ```

   The server calls `http://127.0.0.1:8000` by default; set `OLMENTA_API_URL` to use another local port.

3. Note the **absolute path** to `backend/`, for example `/Users/you/…/personal-finance-planner/backend`. It's called `<BACKEND>` below.

4. Optionally, check the server starts. It waits silently for a client on stdin, so press Ctrl-C to stop it:

   ```bash
   uv --directory <BACKEND> run python -m mcp_server
   ```

## Claude Code

```bash
claude mcp add olmenta -- uv --directory <BACKEND> run python -m mcp_server
```

- Run `/mcp` inside Claude Code to check that `olmenta` is connected and lists 12 tools.
- Add `--scope user` to have it in every project, not only this one.
- For another API port, add `-e OLMENTA_API_URL=http://127.0.0.1:8001` before `--`.
- To remove it: `claude mcp remove olmenta`.

## Claude Desktop

1. Find uv's absolute path, because Claude Desktop doesn't use your shell's `PATH`:

   ```bash
   which uv   # e.g. /Users/you/.local/bin/uv
   ```

2. Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and add:

   ```json
   {
     "mcpServers": {
       "olmenta": {
         "command": "/Users/you/.local/bin/uv",
         "args": ["--directory", "<BACKEND>", "run", "python", "-m", "mcp_server"]
       }
     }
   }
   ```

3. Quit and reopen Claude Desktop. The Olmenta tools appear in the chat's tools/connectors menu.

4. Claude asks before each tool call. You can allow the read tools always and approve the writes one by one.

## ChatGPT (through OpenAI's Secure MCP Tunnel)

ChatGPT can't start a program on your computer. OpenAI's **Secure MCP Tunnel** bridges that gap:

- a small `tunnel-client` runs locally and starts this same stdio server;
- it keeps an **outbound-only** connection to OpenAI;
- nothing on your machine is exposed to the internet.

**You need:**

- a ChatGPT plan with **developer mode** for connectors (check your plan's settings);
- an OpenAI Platform account, to create the tunnel.

**Steps:**

1. **Create the tunnel** in the OpenAI Platform: *Settings → Organization → Tunnels*. Copy its `tunnel_id`. Create an API key with the Tunnels **Read** and **Use** permissions.

2. **Install `tunnel-client`** from the Tunnels settings page or from [github.com/openai/tunnel-client/releases](https://github.com/openai/tunnel-client/releases/latest).

3. **Set up a profile** that runs the Olmenta server:

   ```bash
   export CONTROL_PLANE_API_KEY="sk-..."      # the key with Tunnels permissions

   tunnel-client init \
     --sample sample_mcp_stdio_local \
     --profile olmenta \
     --tunnel-id tunnel_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
     --mcp-command "uv --directory <BACKEND> run python -m mcp_server"

   tunnel-client doctor --profile olmenta --explain   # checks the setup
   tunnel-client run --profile olmenta                # keep this running while you chat
   ```

4. **Connect it in ChatGPT:**
   - Turn on developer mode (*Settings → Connectors / Apps → Advanced → Developer mode*).
   - Add a custom MCP server with connection type **Tunnel**, and pick your tunnel or paste the `tunnel_id`.
   - Enable it in a chat.
   - ChatGPT asks you to confirm write actions before running them.

   OpenAI's menu names change from time to time. If a label differs, look for "custom MCP server" or "connector" and the **Tunnel** connection type.

5. **When you're done,** stop `tunnel-client` with Ctrl-C. Without it, ChatGPT can't reach the server.

## Things to ask

| Ask (Spanish or English) | Tool it uses |
|---|---|
| "¿Cómo voy este mes?" / "How's my month going?" | `get_month_overview`, `get_budget` |
| "¿Cuánto me queda para restaurantes?" | `get_budget` |
| "Gasté 40 € en Mercadona" / "Cobré la nómina, 2.350 €" | `add_transaction` |
| "Pon 400 € en Supermercado" | `assign` |
| "Me pasé en Ocio, cúbrelo con lo que sobra de Restaurantes" | `move_money` |
| "Pagué 300 € de la Visa desde BBVA" | `create_transfer` |
| "¿Qué tengo sin categorizar? Ayúdame a ordenarlo" | `review_uncategorized` → `apply_review` |
| "Crea una categoría Mascotas en Hogar" | `create_category` |

## The tools

| Tool | What it does |
|---|---|
| `get_budget` | The month's budget: To Be Assigned, income, assigned/spent/available per category, overspending |
| `get_month_overview` | Paid, still to pay (and whether it's covered), left to spend, saved |
| `list_transactions` | A month's transactions; filter by account or uncategorized only |
| `list_categories` | Groups and categories (the model checks names here instead of inventing them) |
| `list_accounts` | Balances, credit card debt and what's set aside to pay it |
| `review_uncategorized` | Every uncategorized transaction with AI suggestions and matching transfers (runs the backend's AI, so it may take a few seconds) |
| `add_transaction` | Add an expense or income |
| `assign` | Set a category's assigned amount for a month |
| `move_money` | Move money between categories, or from To Be Assigned |
| `create_category` | Create a category in an existing group |
| `create_transfer` | Move money between your accounts (including paying a card) |
| `apply_review` | Resolve uncategorized rows: category, payee, note, transfer, or link to the matching transfer |

Conventions the model follows:

- amounts in euros (`40` or `"12,50"`);
- categories, groups and accounts by **name**: an unknown or ambiguous name returns the candidates instead of guessing;
- results in the es-ES format.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "The Olmenta API isn't running" | Start it: `cd backend && uv run uvicorn app.main:app --reload` |
| The server exits saying the address isn't local | `OLMENTA_API_URL` must point to `localhost` / `127.0.0.1` |
| Claude Desktop shows no tools | Use absolute paths for `uv` and `<BACKEND>`; restart Desktop; check `~/Library/Logs/Claude/mcp*.log` |
| ChatGPT can't reach the server | `tunnel-client run --profile olmenta` must be running; rerun `tunnel-client doctor --profile olmenta --explain` |
| "No category named …" | Expected: the model should ask you or call `list_categories`. Create the category if you want it |
