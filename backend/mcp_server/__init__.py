"""Olmenta dev MCP server (openspec change: dev-mcp-server).

A local, stdio-only MCP server that lets the developer run their own budget
from an LLM client (Claude Code, Claude Desktop, ChatGPT through OpenAI's
Secure MCP Tunnel). Every tool is a thin client over the local REST API —
no database access, no business rules, no LLM calls of its own.
"""
