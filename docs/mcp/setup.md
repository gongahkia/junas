# Junas MCP Setup

Junas exposes a local MCP server named `junas-mcp`. It lets MCP clients call
SG-LegalBench and local SG legal utilities without leaving chat.

## Requirements

- Python 3.11+
- Project dependencies installed from `backend/pyproject.toml`
- Optional local data:
  - `make ingest-sso` for statute lookup
  - `make download-data` for case retrieval
- Optional BYOK variables for other Junas workflows:
  - `AZURE_OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY`

The MCP `run_benchmark` tool is local and deterministic. It validates the
requested model label but does not make external LLM calls.

## Start the server

From the repository root:

```bash
make mcp
```

For streamable HTTP instead of stdio:

```bash
make mcp MCP_HTTP=1
```

The HTTP server listens on `127.0.0.1:3344`.

## Claude Desktop config

Add this server to Claude Desktop's MCP config.

macOS path:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Linux path:

```text
~/.config/Claude/claude_desktop_config.json
```

Windows path:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

Example config:

```json
{
  "mcpServers": {
    "junas-mcp": {
      "command": "/absolute/path/to/junas/.venv/bin/python",
      "args": ["-m", "backend.mcp.server"],
      "cwd": "/absolute/path/to/junas",
      "env": {
        "AZURE_OPENAI_API_KEY": "optional",
        "JUNAS_SSO_JSONL": "/absolute/path/to/junas/backend/vendor-data/sso/statutes.jsonl"
      }
    }
  }
}
```

If you use `uv`, set `command` to `uv` and use:

```json
{
  "args": ["run", "--project", "backend", "python", "-m", "backend.mcp.server"],
  "cwd": "/absolute/path/to/junas"
}
```

## Verify

Restart Claude Desktop, then ask:

```text
Call the junas-mcp health tool.
```

Expected result: server name, repo version, git SHA, and Python version.

Then ask:

```text
List junas-mcp tools.
```

Expected tools:

- `health`
- `run_benchmark`
- `verify_citation`
- `lookup_statute`
- `retrieve_cases`
- `check_compliance`
