# Junas MCP Troubleshooting

## Claude Desktop does not show `junas-mcp`

- Confirm the JSON config is valid.
- Use an absolute `cwd` pointing at the repo root.
- Use an absolute Python or `uv` command path.
- Restart Claude Desktop after config changes.

## `ModuleNotFoundError: mcp`

Install backend dependencies:

```bash
cd backend
uv sync
```

Or install from `backend/pyproject.toml` with your usual Python tooling.

## `ModuleNotFoundError: backend`

The server must run from the repository root when invoked as:

```bash
python -m backend.mcp.server
```

Set `cwd` in Claude Desktop to the repo root.

## `lookup_statute` says SSO JSONL is missing

Populate the local SSO corpus:

```bash
make ingest-sso
```

Or set:

```bash
export JUNAS_SSO_JSONL=/absolute/path/to/statutes.jsonl
```

## `retrieve_cases` says the corpus is unavailable

Populate local retrieval data:

```bash
make download-data
```

The tool also needs the local model/index dependencies used by the existing
case retrieval service.

## `run_benchmark` says a dataset is missing

Build the dataset for that task, for example:

```bash
make build-sglb-16
```

The benchmark tool intentionally runs local/oracle harness tasks. It validates
`model` as one of `azure`, `anthropic`, `gemini`, or `ollama`, but it does not
make paid provider calls.

## HTTP transport does not respond

Start HTTP mode:

```bash
make mcp MCP_HTTP=1
```

The server binds to `127.0.0.1:3344`.
